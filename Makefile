IMAGE ?= anything-important
LLM_URL ?= http://host.containers.internal:11434
GMAIL_CREDENTIALS ?= $(HOME)/.config/anything-important/oauth_credentials.json

.PHONY: build run

build:
	podman build -t $(IMAGE) .

run:
	podman run --rm \
	  --network host \
	  --env-file .env \
	  -v $(GMAIL_CREDENTIALS):/credentials/oauth_credentials.json:ro,Z \
	  $(IMAGE)
