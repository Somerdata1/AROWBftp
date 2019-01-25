from setuptools import setup as sup,find_packages
from setuptools.extension import Extension
import sys

if sys.platform == 'win32':
    USE_CYTHON = True
else:
    USE_CYTHON = True

ext= '.pyx' if USE_CYTHON else '.c'
sourcefiles=['BFTPSocket'+ext]
extensions= [Extension('BFTPSocket',sourcefiles)]
if USE_CYTHON:
   from Cython.Build import cythonize
   extensions= cythonize(extensions)


sup(NameError="AROWBftp",
      version ="2.0.0",
      packages = find_packages(),
      ext_modules=extensions)
#setup(ext_modules=cythonize(extensions,cython_gdb=True))
print ("setup complete")
