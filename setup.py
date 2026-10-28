from setuptools import Extension, setup

try:
    from Cython.Build import cythonize
    USE_CYTHON = True
except ImportError:
    USE_CYTHON = False

ext = ".pyx" if USE_CYTHON else ".c"

extensions = [
    Extension(
        "chronosmatch._matching_core",
        [f"src/chronosmatch/_matching_core{ext}"],
    )
]

if USE_CYTHON:
    ext_modules = cythonize(
        extensions,
        compiler_directives={"language_level": "3"},
    )
else:
    ext_modules = extensions

setup(
    ext_modules=ext_modules,
)
