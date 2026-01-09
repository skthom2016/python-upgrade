"""
SecurePythonUpgradeProject - Python Upgrade Compatibility Analyzer

A Windows-native, offline static analysis tool for detecting Python version
compatibility issues when upgrading between Python versions.
"""

from setuptools import setup, find_packages
import os

# Read the README file
def read_file(filename):
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, filename), encoding='utf-8') as f:
        return f.read()

setup(
    name='bini-python-upgrade',
    version='1.0.0',
    author='SecurePythonUpgradeProject Team',
    description='Python Upgrade Compatibility Analyzer',
    long_description=read_file('README.md'),
    long_description_content_type='text/markdown',
    url='https://github.com/yourusername/bini-py-upgrade',
    packages=find_packages(exclude=['tests', 'tests.*', 'output']),
    py_modules=['bini_analyzer'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Software Development :: Testing',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Operating System :: Microsoft :: Windows',
    ],
    python_requires='>=3.8',
    install_requires=[
        'psutil>=5.9.0',
        'pyyaml>=6.0',
        'packaging>=21.0',
    ],
    entry_points={
        'console_scripts': [
            'bini-analyzer=bini_analyzer:main',
        ],
    },
    include_package_data=True,
    package_data={
        'bini_python_upgrade': [
            'config/*.yaml',
            'rules/**/*.yaml',
            'rules/**/*.yml',
            'reporting/templates/*.html',
            'reporting/static/css/*.css',
            'reporting/static/js/*.js',
        ],
    },
    keywords='python upgrade compatibility static analysis ast',
    project_urls={
        'Bug Reports': 'https://github.com/yourusername/bini-py-upgrade/issues',
        'Source': 'https://github.com/yourusername/bini-py-upgrade',
    },
)
