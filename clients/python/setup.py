from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="license-client",
    version="1.0.0",
    author="Mercedes-Benz",
    description="License server client library for Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    py_modules=["license_client"],
    python_requires=">=3.7",
    install_requires=[
        "requests>=2.28.0",
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)

