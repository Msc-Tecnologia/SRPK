from setuptools import setup, find_packages

setup(
    name="srpk",
    version="3.1.0",
    description="Enterprise Python Code Analysis System",
    py_modules=["srpk_v3_1"],
    install_requires=[
        "torch>=1.9.0",
        "numpy>=1.19.0",
        "psutil>=5.8.0",
    ],
    python_requires=">=3.8",
)
