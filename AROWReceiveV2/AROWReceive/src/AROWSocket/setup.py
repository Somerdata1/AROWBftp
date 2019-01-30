try:
    from setuptools import setup ,find_packages
    from setuptools.extension import Extension
    import sys
    
except:
    print("Import Error")
if sys.platform == 'win32':
    USE_CYTHON = True #change this to false if no cython compiler is available
else:
    USE_CYTHON = True

ext= '.pyx' if USE_CYTHON else '.c'
sourcefiles=['BFTPSocket'+ext]
extensions= [Extension('BFTPSocket',sourcefiles)]
if USE_CYTHON:
    try:
        from Cython.Build import cythonize
        extensions= cythonize(extensions,compiler_directives={'language_level' : "3"})
    except:
        print("Cython not available")
        exit(1)
try:
    setup(name="AROWBftp",
        version ="2.0.0",
        packages = find_packages(),
        ext_modules=extensions)
#setup(ext_modules=cythonize(extensions,cython_gdb=True))
    print ("setup complete")
except Exception as e:
    print("setup failed "+e)