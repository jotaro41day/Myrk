from .ir import Instruction, Module, Value
from .neural import kernel, batch_kernel
from .optimize import batch_populations
from .runtime_cpu import PTHREAD_RUNTIME
from .models import STATE_QUERIES, population_type, prefix
from .model_kernels import kernel as model_kernel


C_TYPES = {"i32": "int32_t", "f32": "float", "f64": "double", "bool": "bool"}


class CGenerator:
    def __init__(self):
        self.next_loop = 0
        self.next_temp = 0
        self.resources = []
        self.loop_scopes = []

    def cleanup(self, resources, indent):
        return [f"{'    ' * indent}free({name});" for name in reversed(resources)]

    def block(self, body, indent):
        self.resources.append([])
        lines = []
        for item in body:
            lines.extend(self.statement(item, indent))
        lines.extend(self.cleanup(self.resources.pop(), indent))
        return lines

    def temporary(self, dtype: str, expression: str, indent: int) -> tuple[str, str]:
        name = f"myrk_t_{self.next_temp}"
        self.next_temp += 1
        return f"{'    ' * indent}{C_TYPES[dtype]} {name} = {expression};", name

    def value(self, item: Value, indent: int) -> tuple[list[str], str]:
        if item.op == "spikes":
            return [], f"{item.data}.spikes"
        if item.op in STATE_QUERIES:
            lines, index = self.value(item.args[0], indent)
            field = STATE_QUERIES[item.op]
            assignment, name = self.temporary(item.dtype,
                f"{item.data}.{field}[myrk_index({index}, {item.data}.size)]", indent)
            return lines + [assignment], name
        if item.op == "load":
            lines, index = self.value(item.args[0], indent)
            assignment, name = self.temporary(item.dtype,
                f"{item.data}[myrk_index({index}, {item.data}_size)]", indent)
            return lines + [assignment], name
        if item.op == "constant":
            if item.dtype == "bool":
                return [], "true" if item.data else "false"
            if item.dtype == "f32":
                return [], f"{item.data}f"
            return [], str(item.data)
        if item.op == "variable":
            return [], item.data
        if item.op == "call":
            lines = []
            args = []
            for arg in item.args:
                prelude, rendered = self.value(arg, indent)
                lines.extend(prelude)
                assignment, name = self.temporary(arg.dtype, rendered, indent)
                lines.append(assignment)
                args.append(name)
            assignment, name = self.temporary(item.dtype,
                                              f"myrk_f_{item.data}({', '.join(args)})", indent)
            lines.append(assignment)
            return lines, name
        if item.op == "unary":
            lines, arg = self.value(item.args[0], indent)
            assignment, name = self.temporary(item.dtype, f"({item.data}{arg})", indent)
            return lines + [assignment], name
        if item.op == "logical":
            lines, left = self.value(item.args[0], indent)
            assignment, result = self.temporary("bool", left, indent)
            lines.append(assignment)
            pad = "    " * indent
            condition = result if item.data == "&&" else f"!{result}"
            lines.append(f"{pad}if ({condition}) {{")
            right_lines, right = self.value(item.args[1], indent + 1)
            lines.extend(right_lines)
            lines.extend([f"{pad}    {result} = {right};", f"{pad}}}"])
            return lines, result
        if item.op == "binary":
            left_lines, left = self.value(item.args[0], indent)
            left_assignment, left = self.temporary(item.args[0].dtype, left, indent)
            right_lines, right = self.value(item.args[1], indent)
            right_assignment, right = self.temporary(item.args[1].dtype, right, indent)
            lines = left_lines + [left_assignment] + right_lines + [right_assignment]
            if item.data in ("/", "%") and item.args[0].dtype == "i32":
                helper = "div" if item.data == "/" else "mod"
                expression = f"myrk_{helper}_i32({left}, {right})"
            else:
                expression = f"({left} {item.data} {right})"
            assignment, name = self.temporary(item.dtype, expression, indent)
            return lines + [assignment], name
        raise AssertionError(item.op)

    def statement(self, item: Instruction, indent: int) -> list[str]:
        pad = "    " * indent
        if item.op == "if":
            condition, body, otherwise = item.args
            lines, value = self.value(condition, indent)
            lines.append(f"{pad}if ({value}) {{")
            lines.extend(self.block(body, indent + 1))
            if otherwise:
                lines.append(f"{pad}}} else {{")
                lines.extend(self.block(otherwise, indent + 1))
            lines.append(f"{pad}}}")
            return lines
        if item.op == "while":
            lines = [f"{pad}while (true) {{"]
            condition_lines, condition = self.value(item.args[0], indent + 1)
            lines.extend(condition_lines)
            lines.append(f"{pad}    if (!({condition})) break;")
            self.loop_scopes.append(len(self.resources))
            lines.extend(self.block(item.args[1], indent + 1))
            self.loop_scopes.pop()
            lines.append(f"{pad}}}")
            return lines
        if item.op in ("break", "continue"):
            resources = [name for scope in self.resources[self.loop_scopes[-1]:] for name in scope]
            return self.cleanup(resources, indent) + [f"{pad}{item.op};"]
        if item.op == "advance":
            name, dtype, accumulator = item.data
            start_lines, start = self.value(item.args[0], indent + 1)
            assignment, start = self.temporary("i32", start, indent + 1)
            lines = [f"{pad}{{"] + start_lines + [assignment]
            end_lines, end = self.value(item.args[1], indent + 1)
            assignment, end = self.temporary("i32", end, indent + 1)
            lines += end_lines + [assignment]
            count = f"({end} > {start} ? (uint32_t)((int64_t){end} - {start}) : 0)"
            call = f"myrk_izh_{dtype}_advance(&{name}, {count})"
            lines.append(f"{pad}    if ({end} > {start} && (myrk_cpu_threads() > 1 || myrk_cpu_tile() > 0)) {{")
            if accumulator:
                lines.append(f"{pad}        {accumulator} = (int32_t)((uint32_t){accumulator} + (uint32_t){call});")
            else:
                lines.append(f"{pad}        (void){call};")
            lines.append(f"{pad}    }} else {{")
            original = item.args[2]
            fallback = Instruction("for", item.pos, original.data,
                (Value("variable","i32",item.pos,start),
                 Value("variable","i32",item.pos,end),original.args[2]))
            lines.extend(self.statement(fallback, indent + 2))
            return lines + [f"{pad}    }}",f"{pad}}}"]
        if item.op == "population":
            spec = item.data
            name = spec.name
            lines, size = self.value(spec.size, indent)
            lines += [f"{pad}{population_type(spec.model,spec.precision)} {name};",
                      f"{pad}{name}.size = {size};", f"{pad}{name}.spikes = 0;"]
            for parameter in spec.parameters:
                _, value = self.value(parameter.value, indent)
                lines.append(f"{pad}{name}.{parameter.name} = {value};")
            for state in spec.states:
                lines.append(f"{pad}{name}.{state} = myrk_alloc({name}.size, sizeof({C_TYPES[spec.precision]}));")
                self.resources[-1].append(f"{name}.{state}")
            if spec.model == "Izhikevich":
                lines += [f"{pad}for (int32_t i = 0; i < {name}.size; ++i) {{",
                          f"{pad}    {name}.v[i] = {name}.c;",
                          f"{pad}    {name}.u[i] = {name}.b * {name}.c;", f"{pad}}}"]
            else:
                lines.append(f"{pad}{prefix(spec.model,spec.precision)}_initialize(&{name});")
            return lines
        if item.op == "step":
            name, dtype, model = item.data
            if model != "Izhikevich":
                return [f"{pad}{name}.spikes = {prefix(model,dtype)}_step(&{name});"]
            args = ', '.join(f"{name}.{field}" for field in ("size", "v", "u", "a", "b", "c", "d", "dt", "current"))
            return [f"{pad}{name}.spikes = myrk_izh_{dtype}_step({args});"]
        if item.op == "buffer":
            name, dtype = item.data
            lines, size = self.value(item.args[0], indent)
            self.resources[-1].append(name)
            return lines + [f"{pad}int32_t {name}_size = {size};",
                f"{pad}{C_TYPES[dtype]} *{name} = myrk_alloc({name}_size, sizeof({C_TYPES[dtype]}));"]
        if item.op == "store":
            lines, index = self.value(item.args[0], indent)
            assignment, index = self.temporary("i32",
                f"myrk_index({index}, {item.data}_size)", indent)
            lines.append(assignment)
            value_lines, value = self.value(item.args[1], indent)
            return lines + value_lines + [f"{pad}{item.data}[{index}] = {value};"]
        if item.op == "declare":
            cname, dtype = item.data
            lines, value = self.value(item.args[0], indent)
            return lines + [f"{pad}{C_TYPES[dtype]} {cname} = {value};"]
        if item.op == "assign":
            lines, value = self.value(item.args[0], indent)
            return lines + [f"{pad}{item.data} = {value};"]
        if item.op == "return":
            lines, value = self.value(item.args[0], indent)
            assignment, value = self.temporary(item.args[0].dtype, value, indent)
            cleanup = self.cleanup([name for scope in self.resources for name in scope], indent)
            return lines + [assignment] + cleanup + [f"{pad}return {value};"]
        if item.op == "print":
            value = item.args[0]
            lines, rendered = self.value(value, indent)
            fmt = {"i32": '"%d\\n"', "f32": '"%.9g\\n"',
                   "f64": '"%.17g\\n"', "bool": '"%s\\n"'}[value.dtype]
            if value.dtype == "i32":
                rendered = f"(int)({rendered})"
            elif value.dtype == "f32":
                rendered = f"(double)({rendered})"
            elif value.dtype == "bool":
                rendered = f"({rendered}) ? \"true\" : \"false\""
            return lines + [f"{pad}printf({fmt}, {rendered});"]
        if item.op == "for":
            loop_id = self.next_loop
            self.next_loop += 1
            start, end, body = item.args
            start_lines, start_value = self.value(start, indent + 1)
            end_lines, end_value = self.value(end, indent + 1)
            lines = [f"{pad}{{"] + start_lines + [
                     f"{pad}    int32_t myrk_start_{loop_id} = {start_value};"] + end_lines + [
                     f"{pad}    int32_t myrk_end_{loop_id} = {end_value};",
                     f"{pad}    for (int32_t {item.data} = myrk_start_{loop_id}; "
                     f"{item.data} < myrk_end_{loop_id}; ++{item.data}) {{"]
            self.loop_scopes.append(len(self.resources))
            lines.extend(self.block(body, indent + 2))
            self.loop_scopes.pop()
            lines.extend((f"{pad}    }}", f"{pad}}}"))
            return lines
        raise AssertionError(item.op)

    def generate(self, module: Module) -> str:
        lines = ["// Generated by Myrk 0.1.0; do not edit.",
                 "#include <stdbool.h>", "#include <stdint.h>",
                 "#include <stdio.h>", "#include <stdlib.h>",
                 "#include <limits.h>",
                 "#include <math.h>",
                 "static void *myrk_alloc(int32_t n, size_t width) {",
                 "    if (n < 0 || (size_t)n > SIZE_MAX / width) {",
                 '        fputs("Myrk runtime error: invalid buffer size\\n", stderr); exit(70);',
                 "    }",
                 "    void *p = calloc(n ? (size_t)n : 1, width);",
                 '    if (!p) { fputs("Myrk runtime error: allocation failed\\n", stderr); exit(70); }',
                 "    return p;",
                 "}",
                 "static int32_t myrk_index(int32_t i, int32_t n) {",
                 '    if (i < 0 || i >= n) { fputs("Myrk runtime error: buffer index out of bounds\\n", stderr); exit(70); }',
                 "    return i;",
                 "}",
                 "static int32_t myrk_div_i32(int32_t a, int32_t b) {",
                 "    if (b == 0 || (a == INT32_MIN && b == -1)) {",
                 '        fputs("Myrk runtime error: invalid i32 division\\n", stderr);',
                 "        exit(70);",
                 "    }",
                 "    return a / b;",
                 "}",
                 "static int32_t myrk_mod_i32(int32_t a, int32_t b) {",
                 "    if (b == 0 || (a == INT32_MIN && b == -1)) {",
                 '        fputs("Myrk runtime error: invalid i32 modulo\\n", stderr);',
                 "        exit(70);",
                 "    }",
                 "    return a % b;",
                 "}"]
        def precisions(body):
            for item in body:
                if item.op == "population":
                    yield item.data.model, item.data.precision
                elif item.op == "for":
                    yield from precisions(item.args[2])
                elif item.op == "if":
                    yield from precisions(item.args[1])
                    yield from precisions(item.args[2])
                elif item.op == "while":
                    yield from precisions(item.args[1])
        neural_types = sorted({dtype for p in module.procedures for dtype in precisions(p.body)})
        if neural_types:
            lines.append(PTHREAD_RUNTIME)
        for model,dtype in neural_types:
            if model == "Izhikevich":
                lines.append(kernel(dtype))
                lines.append(batch_kernel(dtype))
            else:
                lines.append(model_kernel(model,dtype))
        for procedure in module.procedures:
            params = ", ".join(f"{C_TYPES[dtype]} {name}" for name, dtype in procedure.params) or "void"
            lines.append(f"static {C_TYPES[procedure.result]} myrk_f_{procedure.name}({params});")
        for procedure in module.procedures:
            params = ", ".join(f"{C_TYPES[dtype]} {name}" for name, dtype in procedure.params) or "void"
            lines.append(f"static {C_TYPES[procedure.result]} myrk_f_{procedure.name}({params}) {{")
            lines.extend(self.block(procedure.body, 1))
            lines.append("}")
        lines.append("int main(void) { return (int)myrk_f_main(); }")
        return "\n".join(lines) + "\n"


def generate(module: Module) -> str:
    return CGenerator().generate(batch_populations(module))
