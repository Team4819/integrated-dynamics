from .types import *
import sympy
sympy.init_printing()


class EulerIntegrator:

    def __init__(self, math_library="numpy"):
        self.state_names = None
        self.state_symbols = None
        self.current_state = None
        self.default_state = None
        self.pose_symbols = None
        self.motion_symbols = None
        self.root_body = None

        self.dt_symbol = None
        self.dt_value = 0.1
        self.time = 0

        self.new_state = None
        self.new_state_mat = None
        self.forward_dynamics_func = None

        self.math_library = math_library

    def init_symbols(self, root_body):
        global substitute_symbols
        self.pose_symbols = root_body.get_pose_symbols()
        self.motion_symbols = root_body.get_motion_symbols()
        self.state_symbols = self.pose_symbols + self.motion_symbols
        self.state_names = root_body.get_pose_symbol_components() + root_body.get_motion_symbol_components()
        self.root_body = root_body
        self.default_state = root_body.get_def_pose_symbol_values() + root_body.get_def_motion_symbol_values()
        self.current_state = self.default_state[:]
        self.dt_symbol = sympy.symbols("dt")
        substitute_symbols = self.build_state_substitutions()

    def build_simulation_expressions(self, root_body):
        self.init_symbols(root_body)
        print("begin c computation")
        # Compute the forward dynamics problem with the Composite-Rigid-Body algorithm
        # Get C (the force vector required for zero acceleration) from the RNEA inverse dynamics solver
        crb_C = Matrix([self.root_body.get_inverse_dynamics([0 for _ in self.motion_symbols])[0]]).T
        #sympy.preview(crb_C, output="dvi")
        print("finished with c, beginning H computation")
        # Get H by CRB
        columns = [None for _ in range(len(self.motion_symbols))]
        for x in reversed(range(len(self.motion_symbols))):
            column = self.root_body.get_inverse_dynamics([1 if x == i else 0 for i in range(len(self.motion_symbols))])[0]
            while len(column) < len(self.motion_symbols):
                column.append(0)
            columns[x] = column
        for y in range(len(self.motion_symbols)):
            for x in range(x+1, len(self.motion_symbols)):
                columns[x][y] = columns[y][x]
        crb_H = Matrix(columns).T
        print(crb_H.evalf(subs=self.build_state_substitutions()))
        print("Finished with H")
        forces = Matrix([self.root_body.get_total_forces()]).T
        print("begin solve")
        joint_accel = crb_H.LUsolve(forces-crb_C)
        print("end solve")

        joint_dv = joint_accel*self.dt_symbol
        new_joint_motion = [self.motion_symbols[x] + joint_dv[x, 0] for x in range(len(joint_dv))]
        print("begin motion integration")
        new_joint_pose = self.root_body.integrate_motion(self.motion_symbols, self.dt_symbol)
        print("end motion integration")
        self.new_state = new_joint_pose + new_joint_motion
        self.new_state_mat = Matrix([self.new_state])

    def build_simulation_functions(self):
        if self.math_library == "theano":
            from sympy.printing.theanocode import theano_function
            print("building theano function")
            self.forward_dynamics_func = theano_function(self.state_symbols + [self.dt_symbol], self.new_state)
            print("finished building theano function")
        else:
            print("begin lambdification")
            if self.math_library == "numpy":
                # TODO: remove workaround when fixed https://github.com/sympy/sympy/issues/11306
                args = [self.dt_symbol]
                for arg in self.state_symbols:
                    args.append(numpy.asarray(arg))
            self.forward_dynamics_func = sympy.lambdify(
                args,
                self.new_state_mat,
                modules=self.math_library,
                dummify=False)
            print("finish lambdification")

    def build_state_substitutions(self):
        subs = {
            self.dt_symbol: self.dt_value
        }
        for i in range(len(self.state_symbols)):
            subs[self.state_symbols[i]] = self.current_state[i]
        return subs

    def step_time(self, dt=None):
        if dt is not None:
            self.dt_value = dt
        new_state = self.forward_dynamics_func(*(self.current_state + [self.dt_value]))[0].tolist()
        print(type(new_state))
        self.current_state = new_state
        self.time += self.dt_value

    def get_time(self):
        return self.time

