from Cython.Build import cythonize
from setuptools import Extension, setup

extensions = [
    Extension(
        "chronosmatch._matching_core",
        ["src/chronosmatch/_matching_core.pyx"],
    )
]

setup(
    ext_modules=cythonize(
        extensions,
        compiler_directives={"language_level": "3"},
    ),
)
