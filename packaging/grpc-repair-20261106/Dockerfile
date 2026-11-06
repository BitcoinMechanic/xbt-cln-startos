FROM xbt-grpc-repair-donor:20261106 AS grpc
FROM xbt-grpc-repair-parent:20261106
COPY --from=grpc /usr/local/libexec/c-lightning/plugins/cln-grpc /opt/xbt/libexec/c-lightning/plugins/cln-grpc
RUN echo '0b4774e23b8eb81e79fabc0602a43cc53bac962fe229533098b258fd72a4ae06  /opt/xbt/libexec/c-lightning/plugins/cln-grpc' | sha256sum -c -
