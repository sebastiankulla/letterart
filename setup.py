from setuptools import setup, find_packages

setup(
    name="letterart",
    version="0.1",
    url="https://github.com/sebastiankulla/letterart",
    license="MIT",
    author="Sebastian Kulla",
    author_email="sebastiankulla90@gmail.com",
    description="A tool to make art out of a memorable image and a great backstory.",
    packages=find_packages(),
    install_requires=['Pillow'],
)
