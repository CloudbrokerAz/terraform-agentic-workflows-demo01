FROM srlynch1/terraform-ai-tools:latest

# Install IBM Bob Shell (bobshell) at the latest published version. The COS
# bucket's bobshell-version.txt is the same source of truth the official
# install-bobshell.sh uses; installing the tarball directly keeps the build
# non-interactive.
RUN version=$(curl -fsSL https://s3.us-south.cloud-object-storage.appdomain.cloud/bobshell/bobshell-version.txt) && \
    npm install -g "https://s3.us-south.cloud-object-storage.appdomain.cloud/bobshell/bobshell-${version}.tgz" && \
    npm cache clean --force

# Install pre-commit (base image has uv but not pre-commit)
RUN uv tool install pre-commit --with pre-commit-uv
