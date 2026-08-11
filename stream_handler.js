// SSE Streaming handler for real-time token delivery
class StreamHandler {
    constructor(url, context, callbacks = {}) {
        this.url = url;
        this.context = context;
        this.callbacks = callbacks;
        this.abortController = new AbortController();
        this.tokenBuffer = "";
        this.eventSource = null;
    }

    async connect() {
        try {
            const response = await fetch(`${this.url}/stream`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    query: this.context,
                    tenant_id: "default",
                    top_k: 10,
                    use_rerank: true,
                }),
                signal: this.abortController.signal,
            });

            if (!response.ok) {
                this.onError("Stream connection failed");
                return;
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                this.parseEvents(chunk);
            }
        } catch (error) {
            if (error.name !== "AbortError") {
                this.onError(error.message);
            }
        }
    }

    parseEvents(chunk) {
        this.tokenBuffer += chunk;
        const events = this.tokenBuffer.split("\n\n");

        for (let i = 0; i < events.length - 1; i++) {
            this.processEvent(events[i]);
        }

        this.tokenBuffer = events[events.length - 1];
    }

    processEvent(eventText) {
        const lines = eventText.split("\n");
        let eventType = "";
        let data = "";

        for (const line of lines) {
            if (line.startsWith("event:")) {
                eventType = line.substring(6).trim();
            } else if (line.startsWith("data:")) {
                data = line.substring(5).trim();
            }
        }

        if (!eventType || !data) return;

        try {
            const payload = JSON.parse(data);
            switch (eventType) {
                case "token":
                    this.onToken(payload.text);
                    break;
                case "metadata":
                    this.onMetadata(payload);
                    break;
                case "progress":
                    this.onProgress(payload);
                    break;
                case "complete":
                    this.onComplete(payload);
                    break;
                case "error":
                    this.onError(payload.error);
                    break;
            }
        } catch (e) {
            console.error("Event parse error:", e);
        }
    }

    onToken(text) {
        if (this.callbacks.onToken) {
            this.callbacks.onToken(text);
        }
    }

    onMetadata(data) {
        if (this.callbacks.onMetadata) {
            this.callbacks.onMetadata(data);
        }
    }

    onProgress(data) {
        if (this.callbacks.onProgress) {
            this.callbacks.onProgress(data.progress);
        }
    }

    onComplete(data) {
        if (this.callbacks.onComplete) {
            this.callbacks.onComplete(data);
        }
    }

    onError(message) {
        if (this.callbacks.onError) {
            this.callbacks.onError(message);
        }
    }

    cancel() {
        this.abortController.abort();
    }
}
