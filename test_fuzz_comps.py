import ast
import pytest
import subprocess
import sys
import tempfile
import textwrap
from astor import to_source  # type: ignore
from pathlib import Path
import time

import evalserver
from hypothesis import given, settings, strategies as st, target, HealthCheck


@pytest.fixture(scope="module")
def logfile(request):
    filepath = request.config.getoption("--logfile") or None
    if filepath:
        with open(filepath, "w") as fh:
            yield fh
    else:
        yield None


@pytest.fixture(scope="module")
def evalserver_client(request, logfile):
    port = request.config.getoption("--port") or 9999
    python = request.config.getoption("--python") or sys.executable
    proc = subprocess.Popen(
        [python, evalserver.__file__, "-p", str(port)], stdout=logfile, stderr=logfile
    )
    time.sleep(1)
    try:
        with evalserver.EvalServerClient(port) as client:
            yield client
    finally:
        proc.terminate()
        proc.wait()


def record_targets(tree: ast.Module) -> ast.Module:
    nodes = list(ast.walk(tree))
    num_lambdas = 0
    num_listcomps = 0
    num_classes = 0
    for n in nodes:
        if isinstance(n, ast.Lambda):
            num_lambdas += 1
        elif isinstance(n, ast.ListComp):
            num_listcomps += 1
        elif isinstance(n, ast.ClassDef):
            num_classes += 100
    # hypothesis will aim for samples that maximize these metrics
    for value, label in [
        (num_lambdas, "(modules) number of lambdas"),
        (num_listcomps, "(modules) number of listcomps"),
        (num_classes, "(modules) number of classes"),
    ]:
        target(float(value), label=label)
    return to_source(tree)


def has_listcomp(tree: ast.Module) -> bool:
    return bool(any(isinstance(n, ast.ListComp) for n in ast.walk(tree)))


def compilable(tree: ast.Module) -> bool:
    codestr = to_source(tree)
    try:
        compile(codestr, "<string>", "exec")
    except Exception:
        return False
    return True


def identifiers():
    return st.one_of(
        st.just("a"),
        st.just("b"),
        # st.just("c"),
        # st.just("x"),
        # st.just("y"),
        # st.just("z"),
    )


st.register_type_strategy(ast.Name, st.builds(ast.Name, identifiers()))
st.register_type_strategy(
    ast.Constant, st.builds(ast.Constant, st.integers(min_value=1, max_value=10))
)
st.register_type_strategy(
    ast.List,
    st.builds(
        ast.List,
        st.lists(
            st.one_of(st.from_type(ast.Name), st.from_type(ast.Constant)),
            min_size=0,
            max_size=3,
        ),
    ),
)
st.register_type_strategy(
    ast.Tuple,
    st.builds(
        ast.Tuple,
        st.lists(
            st.one_of(st.from_type(ast.Name), st.from_type(ast.Constant)),
            min_size=0,
            max_size=3,
        ),
    ),
)


def target_expr():
    return st.one_of(
        st.from_type(ast.Name),
        st.from_type(ast.Subscript),
    )


def value_expr():
    return st.one_of(
        st.from_type(ast.Constant),
        st.from_type(ast.Name),
        listcomps(),
        st.from_type(ast.Lambda),
        st.from_type(ast.Subscript),
        st.from_type(ast.NamedExpr),
        st.from_type(ast.List),
        st.from_type(ast.Tuple),
    )


def iterable_expr():
    return st.one_of(
        st.from_type(ast.List),
        st.from_type(ast.Tuple),
        st.from_type(ast.Name),
        st.from_type(ast.Subscript),
        listcomps(),
    )


@st.composite
def namedexprs(draw):
    target = draw(st.from_type(ast.Name))
    target.ctx = ast.Store()
    value = draw(value_expr())
    return ast.NamedExpr(target, value)


st.register_type_strategy(ast.NamedExpr, namedexprs())


@st.composite
def subscripts(draw):
    value = draw(value_expr())
    index = draw(value_expr())
    return ast.Subscript(value, index)


st.register_type_strategy(ast.Subscript, subscripts())


@st.composite
def lambdas(draw):
    body = draw(value_expr())
    arg_names = draw(st.sets(identifiers(), min_size=0, max_size=3))
    args = ast.arguments(args=[ast.arg(name) for name in arg_names], defaults=[])
    return ast.Lambda(args, body)


st.register_type_strategy(ast.Lambda, lambdas())


@st.composite
def comprehensions(draw):
    target = draw(target_expr())
    iter_ = draw(iterable_expr())
    ifs = draw(st.lists(value_expr(), min_size=0, max_size=2))
    return ast.comprehension(target, iter_, ifs)


st.register_type_strategy(ast.comprehension, comprehensions())


@st.composite
def listcomps(draw):
    elt = draw(value_expr())
    gens = draw(st.lists(st.from_type(ast.comprehension), min_size=1, max_size=3))
    return ast.ListComp(elt, gens)


st.register_type_strategy(ast.ListComp, listcomps())
st.register_type_strategy(
    ast.List, st.builds(ast.List, st.lists(value_expr(), min_size=0, max_size=3))
)
st.register_type_strategy(
    ast.Tuple, st.builds(ast.Tuple, st.lists(value_expr(), min_size=0, max_size=3))
)
st.register_type_strategy(
    ast.Expr,
    st.builds(ast.Expr, value_expr()),
)
st.register_type_strategy(
    ast.Global,
    st.builds(ast.Global, st.lists(identifiers(), min_size=1, max_size=3)),
)
st.register_type_strategy(
    ast.Nonlocal,
    st.builds(ast.Nonlocal, st.lists(identifiers(), min_size=1, max_size=3)),
)


@st.composite
def assigns(draw):
    targets = draw(st.lists(target_expr(), min_size=1, max_size=2))
    value = draw(value_expr())
    return ast.Assign(targets, value)


st.register_type_strategy(ast.Assign, assigns())


def statements():
    return st.one_of(
        st.from_type(ast.Assign),
        st.from_type(ast.Nonlocal),
        st.from_type(ast.Global),
        st.from_type(ast.Expr),
        st.from_type(ast.FunctionDef),
        classes(),
    )


@st.composite
def classes(draw):
    name = draw(identifiers())
    stmts = draw(st.lists(statements(), min_size=1, max_size=10))
    return ast.ClassDef(name, body=stmts, decorator_list=[], bases=[])


st.register_type_strategy(ast.ClassDef, classes())


@st.composite
def functions(draw):
    name = draw(identifiers())
    arg_names = draw(st.sets(identifiers(), min_size=0, max_size=3))
    args = ast.arguments(args=[ast.arg(name) for name in arg_names], defaults=[])
    stmts = draw(st.lists(statements(), min_size=1, max_size=10))
    return ast.FunctionDef(name, args, stmts, [])


st.register_type_strategy(ast.FunctionDef, functions())


def module_level_statements():
    return st.one_of(
        # st.from_type(ast.Assign),
        # st.from_type(ast.FunctionDef),
        st.from_type(ast.ClassDef),
    )


st.register_type_strategy(
    ast.Module,
    st.builds(ast.Module, st.lists(module_level_statements(), min_size=1, max_size=1)),
)


def modules():
    return (
        st.from_type(ast.Module)
        .filter(has_listcomp)
        .filter(compilable)
        .map(record_targets)
    )


@given(modules())
@settings(
    max_examples=100_000,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_comprehension(
    request, logfile, evalserver_client: evalserver.EvalServerClient, codestr: str
):
    if logfile:
        logfile.write(codestr)
        logfile.write("\n")
        logfile.flush()
    my_result = evalserver.try_eval(codestr.encode())
    remote_result = evalserver_client.submit_code(codestr)
    assert my_result == remote_result
