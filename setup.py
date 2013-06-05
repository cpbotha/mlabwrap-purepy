from setuptools import setup, find_packages

setup(
    name='mlabwrap-purepy',
    version='0.1',
    description='Slightly improved fork of the pure Python mlabwrap Python to Matlab bridge.',
    long_description=open('README.rst').read(),
    author='Charl P. Botha',
    author_email='cpbotha@vxlabs.com',
    url='https://github.com/cpbotha/mlabwrap-purepy',
    license='MIT',
    keywords = "python matlab",
    # gets nested packages also, including
    # django_shell_ipynb.management.commands
    packages=find_packages(),
    # on Windows it only seems to need numpy
    # on Linux it needs both numpy and scipy
    install_requires = ['numpy', 'scipy'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)