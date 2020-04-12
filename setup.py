from setuptools import setup


with open('README.md', 'r') as f:
    long_description = f.read()


setup(
    name='anakin-language-server',
    version='1.0',
    author='Andrii Kolomoiets',
    author_email='andreyk.mad@gmail.com',
    description='Yet another Jedi Python language server',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/muffinmad/anakin-language-server',
    packages=['anakinls'],
    python_requires='>=3.6',
    install_requires=[
        'jedi==0.16.0',
        'pygls==0.8.1'
    ],
    entry_points={
        'console_scripts': [
            'anakinls=anakinls.__main__:main'
        ]
    }
)
