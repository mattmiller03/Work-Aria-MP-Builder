FROM base-adapter:python-1.2.0

USER root
COPY app/wheels/ /tmp/wheels/
RUN pip install --no-cache-dir --no-index --find-links /tmp/wheels/ requests vmware-aria-operations-integration-sdk-lib && rm -rf /tmp/wheels

COPY commands.cfg .
COPY app app
RUN chmod -R 755 /home/aria-ops-adapter-user/src/app/
RUN chown -R aria-ops-adapter-user:aria-ops-adapter-user /home/aria-ops-adapter-user/src/app/

USER aria-ops-adapter-user
