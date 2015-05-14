""" Setup file for statscache """

from setuptools import setup


def get_description():
    with open('README.rst', 'r') as f:
        return ''.join(f.readlines()[2:])

requires = [
    'fedmsg',
    'fedmsg_meta_fedora_infrastructure',
    'sqlalchemy',
]

tests_require = [
    'nose',
]

setup(
    name='statscache',
    version='0.0.1',
    description='Daemon to build and keep fedmsg statistics',
    long_description=get_description(),
    author='Ralph Bean',
    author_email='rbean@redhat.com',
    url="https://github.com/fedora-infra/statscache/",
    download_url="https://pypi.python.org/pypi/statscache/",
    license='LGPLv2+',
    install_requires=requires,
    tests_require=tests_require,
    test_suite='nose.collector',
    packages=['statscache'],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        'Environment :: Web Environment',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
    ],
    entry_points={
        'moksha.consumer': [
            "statscache_consumer = statscache.consumer:StatsConsumer",
        ],
        'moksha.producer': [
            "statscache_1s_producer = statscache.producer:OneSecondProducer",
            "statscache_5s_producer = statscache.producer:FiveSecondProducer",
            "statscache_1m_producer = statscache.producer:OneMinuteProducer",
        ],
    },
)
