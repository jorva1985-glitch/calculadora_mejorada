#!/usr/bin/env python3
"""
Calculadora avanzada - modo REPL
Soporta:
 - expresiones seguras mediante ast
 - funciones matemáticas (math)
 - decimal para mayor precisión
 - historial y memoria
 - conversiones de unidades
 - asignación simple de variables (a = 3.14)
"""

import ast
import operator as op
import math
from decimal import Decimal, getcontext, InvalidOperation
import readline  # para historial/edición en terminal
import sys

# Ajuste de precisión decimal (puedes cambiar)
getcontext().prec = 28

# --- Operadores permitidos en AST ---
ALLOWED_OPERATORS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.Mod: op.mod,
    ast.USub: op.neg,
    ast.UAdd: op.pos,
    ast.FloorDiv: op.floordiv,
    ast.BitXor: None,  # deshabilitado (por seguridad / no estándar)
}

# --- Funciones matemáticas expuestas ---
MATH_FUNCS = {
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'asin': math.asin,
    'acos': math.acos,
    'atan': math.atan,
    'atan2': math.atan2,
    'sinh': math.sinh,
    'cosh': math.cosh,
    'tanh': math.tanh,
    'exp': math.exp,
    'ln': math.log,      # ln(x) -> log natural
    'log': lambda x, b=10: math.log(x, b),  # log(x) o log(x, base)
    'sqrt': math.sqrt,
    'pow': math.pow,
    'abs': abs,
    'fact': math.factorial,
    'factorial': math.factorial,
    'round': round,
    'floor': math.floor,
    'ceil': math.ceil,
    'deg': math.degrees,
    'rad': math.radians,
}

# --- Conversiones de unidades simples ---
CONVERSIONS = {
    'c_to_f': lambda c: (c * 9/5) + 32,
    'f_to_c': lambda f: (f - 32) * 5/9,
    'c_to_k': lambda c: c + 273.15,
    'k_to_c': lambda k: k - 273.15,
    # longitud (metros, centímetros, kilómetros, pulgadas, pies)
    'm_to_cm': lambda m: m * 100,
    'cm_to_m': lambda cm: cm / 100,
    'm_to_km': lambda m: m / 1000,
    'km_to_m': lambda km: km * 1000,
    'in_to_cm': lambda i: i * 2.54,
    'cm_to_in': lambda cm: cm / 2.54,
    'ft_to_m': lambda ft: ft * 0.3048,
    'm_to_ft': lambda m: m / 0.3048,
    # masa
    'kg_to_g': lambda kg: kg * 1000,
    'g_to_kg': lambda g: g / 1000,
    'lb_to_kg': lambda lb: lb * 0.45359237,
    'kg_to_lb': lambda kg: kg / 0.45359237,
}

# --- Estado de la calculadora ---
history = []
memory = Decimal('0')
variables = {}  # para asignaciones simples

# --- Helpers: convertir a Decimal si es posible ---
def to_decimal(val):
    try:
        if isinstance(val, Decimal):
            return val
        if isinstance(val, (int, float)):
            return Decimal(str(val))
        if isinstance(val, str):
            return Decimal(val)
    except InvalidOperation:
        raise ValueError(f"No se puede convertir '{val}' a Decimal.")
    raise ValueError(f"Tipo no soportado para conversión a Decimal: {type(val)}")


# --- Evaluador AST seguro ---
class Evaluator(ast.NodeVisitor):
    def __init__(self, names):
        self.names = names

    def visit(self, node):
        if isinstance(node, ast.Expression):
            return self.visit(node.body)
        return super().visit(node)

    def visit_BinOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
        op_type = type(node.op)
        if op_type in ALLOWED_OPERATORS and ALLOWED_OPERATORS[op_type] is not None:
            func = ALLOWED_OPERATORS[op_type]
            return func(left, right)
        raise ValueError(f"Operador no permitido: {op_type}")

    def visit_UnaryOp(self, node):
        operand = self.visit(node.operand)
        op_type = type(node.op)
        if op_type in ALLOWED_OPERATORS and ALLOWED_OPERATORS[op_type] is not None:
            func = ALLOWED_OPERATORS[op_type]
            return func(operand)
        raise ValueError(f"Operador unario no permitido: {op_type}")

    def visit_Num(self, node):
        return node.n

    def visit_Constant(self, node):
        # ast.Constant cubre números y strings en Python3.8+
        if isinstance(node.value, (int, float, complex, Decimal)):
            return node.value
        raise ValueError(f"Constante no soportada: {node.value}")

    def visit_Name(self, node):
        if node.id in self.names:
            return self.names[node.id]
        if node.id in MATH_FUNCS:
            return MATH_FUNCS[node.id]
        # permitir constantes pi y e
        if node.id == 'pi':
            return math.pi
        if node.id == 'e':
            return math.e
        raise ValueError(f"Nombre no definido: '{node.id}'")

    def visit_Call(self, node):
        func = self.visit(node.func)
        if not callable(func):
            raise ValueError("Intento de llamada a objeto no callable")
        args = [self.visit(a) for a in node.args]
        # permitir kwargs simples? no, por seguridad
        return func(*args)

    def visit_Assign(self, node):
        raise ValueError("Asignaciones no permitidas en expresiones - use 'a = 3' sintaxis especial")

    def generic_visit(self, node):
        raise ValueError(f"Nodo no permitido en expresión: {type(node).__name__}")


def safe_eval(expr, names=None):
    """
    Evalúa una expresión aritmética/funcional de forma segura usando ast.
    """
    if names is None:
        names = {}
    try:
        parsed = ast.parse(expr, mode='eval')
    except SyntaxError as e:
        raise ValueError("Sintaxis inválida")
    evaluator = Evaluator(names)
    return evaluator.visit(parsed)


# --- Procesamiento de líneas: soporta 'a = expr' para asignar variables ---
def process_line(line):
    line = line.strip()
    if not line:
        return None

    # Comandos especiales
    if line.lower() in (':h', ':help', 'help', 'ayuda'):
        return help_text()
    if line.lower() in (':q', ':quit', 'exit', 'salir'):
        print("Saliendo...")
        sys.exit(0)
    if line.lower() in (':history', 'history'):
        return show_history()
    if line.lower() in (':mem', 'memory'):
        return f"Memoria = {memory}"
    if line.lower() in (':mc',):
        return clear_memory()
    if line.lower().startswith(':convert'):
        # :convert tipo valor  -> ejemplo: :convert c_to_f 100
        parts = line.split()
        if len(parts) < 3:
            return ("Uso: :convert <tipo> <valor>. Tipos disponibles: " +
                    ", ".join(sorted(CONVERSIONS.keys())))
        key = parts[1]
        try:
            val = float(parts[2])
        except Exception:
            return "Valor inválido para conversión."
        if key not in CONVERSIONS:
            return f"Conversión desconocida: {key}"
        res = CONVERSIONS[key](val)
        history.append(f"convert {key}({val}) => {res}")
        return res

    # Memoria: M+, M-, MR, MC (pueden venir solas o separadas)
    if line.upper() in ('M+', 'M-', 'MR', 'MC'):
        return handle_memory_cmd(line.upper())

    # Asignación de variable simple: a = expr
    if '=' in line:
        var_part, expr_part = line.split('=', 1)
        var = var_part.strip()
        if not var.isidentifier():
            return "Nombre de variable inválido."
        val = evaluate_expression(expr_part.strip())
        if isinstance(val, (int, float, Decimal)):
            variables[var] = val
            history.append(f"{var} = {val}")
            return f"{var} = {val}"
        else:
            return "No se puede asignar ese tipo de valor a la variable."

    # Si no es comando ni asignación -> evaluar como expresión
    return evaluate_expression(line)


def evaluate_expression(expr):
    # reemplezar uso de variables por sus valores en un dict seguro
    names = {}
    # agregar variables con sus valores numéricos
    for k, v in variables.items():
        names[k] = float(v) if isinstance(v, (int, float, Decimal)) else v
    # agregar funciones
    for k, v in MATH_FUNCS.items():
        names[k] = v
    names['pi'] = math.pi
    names['e'] = math.e

    try:
        result = safe_eval(expr, names)
        # si viene como float, convertir Decimal para consistencia
        try:
            if isinstance(result, (int, float)):
                dres = Decimal(str(result))
                history.append(f"{expr} => {dres}")
                return dres
            if isinstance(result, Decimal):
                history.append(f"{expr} => {result}")
                return result
            # si la función devolvió algo distinto (como tuple), lo retornamos tal cual
            history.append(f"{expr} => {result}")
            return result
        except InvalidOperation:
            history.append(f"{expr} => {result}")
            return result
    except Exception as e:
        return f"Error: {e}"


def handle_memory_cmd(cmd):
    global memory
    if cmd == 'MR':
        return memory
    if cmd == 'MC':
        memory = Decimal('0')
        return "Memoria borrada."
    if cmd in ('M+', 'M-'):
        # Tomar último resultado del historial
        if not history:
            return "Historial vacío, nada que almacenar."
        last = history[-1]
        # asumimos formato "expr => value" o "convert..."
        if '=>' in last:
            val_str = last.split('=>')[-1].strip()
        else:
            val_str = last
        try:
            val = to_decimal(val_str)
        except Exception:
            return "Último resultado no es un número válido para memoria."
        if cmd == 'M+':
            memory += val
            return f"Memoria = {memory}"
        else:
            memory -= val
            return f"Memoria = {memory}"
    return "Comando de memoria desconocido."


def clear_memory():
    global memory
    memory = Decimal('0')
    return "Memoria limpiada."


def show_history():
    if not history:
        return "Historial vacío."
    out = []
    for i, item in enumerate(history[-50:], start=1):
        out.append(f"{i}: {item}")
    return "\n".join(out)


def help_text():
    return """
Comandos especiales:
  help | :h        -> mostrar esta ayuda
  :history         -> mostrar historial
  :convert tipo v  -> convertir unidades (ej: :convert c_to_f 100)
  :mem / :mc       -> mostrar / limpiar memoria
  M+ / M- / MR / MC -> memoria (usa el último resultado)
  exit | :q        -> salir

Funciones disponibles (ejemplos):
  sin(x), cos(x), tan(x), ln(x), log(x), sqrt(x), pow(x,y), fact(x)
Constantes: pi, e

Asignación: a = 3.5
Ejemplo de expresión: 2 * (3 + sin(pi/4)) - sqrt(9)

Conversiones disponibles: {}
""".format(", ".join(sorted(CONVERSIONS.keys())))


def repl():
    banner = """
Calculadora avanzada (REPL)
Escribe 'help' o ':h' para ver comandos.
Ej.: 2 + 3*4, sin(pi/6), a = 3; luego a * 5
"""
    print(banner)
    try:
        while True:
            try:
                line = input("calc> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nSaliendo...")
                break

            if not line:
                continue

            out = process_line(line)
            if out is None:
                continue
            # Mostrar salidas multilinea correctamente
            if isinstance(out, str) and '\n' in out:
                print(out)
            else:
                print(out)
    except Exception as e:
        print(f"Error inesperado: {e}")


if __name__ == '__main__':
    repl()
