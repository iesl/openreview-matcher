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
        "ortools==8.*",
        "pytest==7.*",
        "sortedcontainers==2.*",
        "Flask==1.*",
        "flask-cors==3.*",
        "cffi==1.*",
        "pre-commit==2.*",
        "celery==5.*",
        "redis==3.*",
        "MarkupSafe==1.*",
        "gunicorn==19.*",
    ],
    extras_require={
        "full": ["flower"],
    },
    zip_safe=False,
)
