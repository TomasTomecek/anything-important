IMAGE ?= anything-important
LLM_URL ?= http://host.containers.internal:11434
GMAIL_CREDENTIALS ?= $(HOME)/.config/anything-important/oauth_credentials.json

.PHONY: build run

build:
	podman build -t $(IMAGE) .

run:
	podman run --rm \
	  --network host \
	  -e TELEGRAM_TOKEN=$(TELEGRAM_TOKEN) \
	  -e TELEGRAM_CHAT_ID=$(TELEGRAM_CHAT_ID) \
	  -e LLM_URL=$(LLM_URL) \
	  -e GMAIL_QUERY='$(GMAIL_QUERY)' \
	  -v $(GMAIL_CREDENTIALS):/credentials/oauth_credentials.json:ro,Z \
	  $(IMAGE)
