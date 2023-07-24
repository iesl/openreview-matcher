from setuptools import setup, find_packages

setup(
    name="openreview-matcher",
    version="1.0",
    description="OpenReview matching library",
    url="https://github.com/openreview/openreview-matcher",
    author="Michael Spector",
    author_email="spector@cs.umass.edu",
    license="MIT",
    packages=["matcher"],
    setup_requires=["cffi>=1.0.0"],
    cffi_modules=[
        "matcher/solvers/bvn_extension/bvn_extension_build.py:ffibuilder"
    ],
    install_requires=[
        "numpy==1.*",
        "openreview-py",
        "ortools==9.*",
        "pytest==7.*",
        "sortedcontainers==2.*",
        "Flask==2.2.5",
        "flask-cors==3.*",
        "cffi==1.*",
        "pre-commit==2.*",
        "celery==5.2.7",
        "redis==3.*",
        "MarkupSafe==2.*",
        "gunicorn==19.*",
        "importlib-metadata>=1.1.0,<4.3",
        "flake8==3.8.4",
        "gurobipy==10.0.1",
        "kombu>=5.3.0,<6.0",
        "psutil",
        "scipy"
    ],
    extras_require={
        "full": ["flower"],
    },
    zip_safe=False,
)
