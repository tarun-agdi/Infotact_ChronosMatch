
from setuptools import setup, Extension, find_packages
from Cython.Build import cythonize

extensions = [
    Extension(
        name="chronosmatch.matching_engine_cy",
        sources=["src/chronosmatch/matching_engine.pyx"],
    )
]

setup(
    name="chronosmatch",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": 3,
            "boundscheck": True,
            "wraparound": True,
        },
    ),
)
