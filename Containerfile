FROM fedora:43

RUN dnf install -y python3 python3-pip && dnf clean all

WORKDIR /app

COPY pyproject.toml .
RUN pip3 install --no-cache-dir -e .

COPY anything_important/ anything_important/

CMD ["anything-important"]
