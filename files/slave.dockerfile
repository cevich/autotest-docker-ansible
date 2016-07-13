FROM docker.io/stackbrew/centos:latest
MAINTAINER Chris Evich <cevich@redhat.com>

# ADEPT relies on loop_control, first available in ansible 2.1
RUN yum install -y epel-release && \
    yum install -y ansible iproute hostname git sed && \
    yum update -y && \
    # Keep every layer as clean (i.e. small) as possible
    yum clean all && \
    rm -rf /usr/src /usr/share/doc && \
    echo "" > /etc/ansible/hosts

# python-shade is not yet available in EPEL, use pip to install (cry).
# Remove this when it becomes avaiable.  List was obtained from
#     http://pkgs.fedoraproject.org/cgit/rpms/python-shade.git/tree/python-shade.spec
RUN  yum install -y https://rdoproject.org/repos/rdo-release.rpm && \
     yum install -y python-dogpile-core \
        python-swiftclient \
        python-heatclient \
        python-ironicclient \
        python-troveclient \
        python-neutronclient \
        python-cinderclient \
        python-glanceclient \
        python-keystoneclient \
        python-novaclient \
        python-six python-ipaddress \
        python-jsonpatch \
        python-decorator \
        python-munch \
        python-keystoneauth1 \
        python-os-client-config \
        python2-requestsexceptions \
        python-netifaces \
        python3-dogpile-cache \
        python3-swiftclient \
        python3-heatclient \
        python3-ironicclient \
        python3-troveclient \
        python3-neutronclient \
        python3-cinderclient \
        python3-glanceclient \
        python3-keystoneclient \
        python3-novaclient \
        python3-six \
        python3-ipaddress \
        python3-jsonpatch \
        python3-decorator \
        python3-munch \
        python3-keystoneauth1 \
        python3-os-client-config \
        python3-requestsexceptions \
        python3-netifaces && \
    rm -rf /usr/src /usr/share/doc && \
    yum clean all

RUN yum install -y python-pip python-devel && \
    yum groupinstall -y 'Development Tools' 'Development Libraries' && \
    pip install --no-cache-dir --disable-pip-version-check shade && \
    yum erase -y python-devel python-pip && \
    yum history && \
    yum history -y undo 9 && \
    yum clean all && \
    rm -rf /usr/src /usr/share/doc

ENTRYPOINT ["/var/lib/adept/adept.py"]
