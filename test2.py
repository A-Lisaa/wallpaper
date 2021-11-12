class Outer:
    class Inner:
        @staticmethod
        def print_a():
            print("a")

        @staticmethod
        def print_d(func):
            @staticmethod
            def inner():
                print("d")
                func()
            return inner

    def print_b(self):
        self.Inner.print_a()
        print("b")

    @Inner.print_d
    def print_c():
        print("c")

Outer().print_b()
Outer().print_c()