'use strict';

class MiningConsole {
    constructor(userDid, reloadChain) {
        this.userDid = userDid;
        this.reloadChain = reloadChain;
        this.job = null;
        this.pending = 0;
        this.ready = false;
        this.sending = false;
        this.timer = null;
        this.version = 0;
        this.detailVersion = 0;
        this.form = document.getElementById('mining-form');
        this.limit = document.getElementById('mining-limit');
        this.start = document.getElementById('mine-btn');
        this.cancel = document.getElementById('mining-cancel');
        this.inspectButton = document.getElementById('mining-inspect');
        this.message = document.getElementById('mine-result');
        this.form.addEventListener('submit', event => {
            event.preventDefault();
            this.send('POST', '/api/mining', {limit: this.limit.value ? this.limit.valueAsNumber : null});
        });
        this.cancel.addEventListener('click', () => this.send('DELETE', '/api/mining/' + this.job.id));
        this.inspectButton.addEventListener('click', () => this.inspect(this.job.block_index, this.job.block_hash));
        document.addEventListener('visibilitychange', () => {
            clearTimeout(this.timer);
            if (!document.hidden && !this.sending) this.refresh();
        });
    }

    setPending(count) {
        this.pending = count;
        this.controls();
        if (!this.job && this.ready) this.message.textContent = this.queueMessage();
    }

    queueMessage() {
        return this.pending ? this.pending.toLocaleString() + ' pending in the queue.'
                            : 'Queue empty. Send a transaction to mine a block.';
    }

    controls() {
        const busy = this.sending || !!this.job?.active;
        this.start.disabled = !this.ready || busy || !this.pending;
        this.limit.disabled = busy;
        this.cancel.hidden = !this.job?.active || this.job.miner_did !== this.userDid;
        this.cancel.disabled = this.sending || !['starting', 'running'].includes(this.job?.state);
        this.inspectButton.hidden = this.job?.state !== 'completed';
    }

    schedule(delay) {
        clearTimeout(this.timer);
        if (!document.hidden) this.timer = setTimeout(() => this.refresh(), delay);
    }

    async refresh() {
        const version = ++this.version;
        try {
            const response = await fetch('/api/mining', {cache: 'no-store'});
            if (!response.ok) throw new Error();
            const {job} = await response.json();
            if (version === this.version) this.display(job);
        } catch {
            if (version !== this.version) return;
            this.ready = false;
            this.controls();
            this.message.textContent = 'Mining status unavailable. Reconnecting…';
            this.schedule(2000);
        }
    }

    async send(method, url, body) {
        if (this.sending) return;
        this.sending = true;
        ++this.version;
        clearTimeout(this.timer);
        this.controls();
        this.message.textContent = method === 'POST' ? 'Starting mining…' : 'Requesting cancellation…';
        try {
            const res = await fetch(url, {
                method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
            });
            const result = await res.json();
            if (!res.ok) throw new Error(result.error || 'Request failed');
            this.display(result.job);
        } catch (error) {
            this.message.textContent = error.message;
            this.schedule(1500);
        } finally {
            this.sending = false;
            this.controls();
        }
    }

    display(job) {
        const previous = this.job;
        this.job = job;
        this.ready = true;
        this.controls();
        const states = {starting:'Starting', running:'Mining', cancelling:'Cancelling', committing:'Confirming',
            completed:'Confirmed', cancelled:'Cancelled', empty:'Queue empty', busy:'Miner busy', failed:'Failed'};
        document.getElementById('mining-state').textContent = job ? states[job.state] : 'Idle';
        document.getElementById('mining-metrics').hidden = !job;
        if (!job) {
            this.message.textContent = this.queueMessage();
            return;
        }
        document.getElementById('mining-attempts').textContent = job.attempts.toLocaleString();
        document.getElementById('mining-rate').textContent = job.hashes_per_second.toLocaleString();
        document.getElementById('mining-elapsed').textContent = job.elapsed_seconds.toFixed(2) + ' s';
        const batch = job.transaction_count + (job.transaction_count === 1 ? ' transaction' : ' transactions');
        const messages = {
            starting:'Preparing the next block.', running:'Working on block #' + job.block_index + ' · ' + batch,
            committing:'Confirming block #' + job.block_index, cancelling:'Stopping this run…',
            completed:'Mined block #' + job.block_index + ' · ' + batch + ' and a mining reward.',
            cancelled:'Mining stopped. Unconfirmed transactions stay in the queue.',
            busy:'Another miner has the ledger. Try again when it finishes.',
            empty:'The queue was mined before this run started.', failed:'Mining failed. You can retry the queue.'
        };
        this.message.textContent = messages[job.state];
        if (job.active) this.schedule(400);
        if (!job.active && (previous?.active || previous?.id !== job.id)) {
            this.reloadChain().catch(() => {});
        }
    }

    async inspect(index, expectedHash) {
        const version = ++this.detailVersion;
        const dialog = document.getElementById('block-dialog');
        const fields = document.getElementById('block-fields');
        const list = document.getElementById('block-transactions');
        const message = document.getElementById('block-message');
        document.getElementById('block-heading').textContent = 'Block #' + index;
        fields.replaceChildren();
        list.replaceChildren();
        message.textContent = 'Loading block…';
        const opener = document.activeElement;
        dialog.addEventListener('hidden.bs.modal', () => opener?.focus(), {once: true});
        bootstrap.Modal.getOrCreateInstance(dialog).show();
        try {
            const res = await fetch('/api/blocks/' + index);
            if (!res.ok) throw new Error('This block is unavailable.');
            const {block} = await res.json();
            if (version !== this.detailVersion) return;
            if (block.hash !== expectedHash) throw new Error('The chain changed. Refresh the dashboard to inspect the current block.');
            const details = [['Hash',block.hash], ['Previous hash',block.previous_hash], ['Nonce',block.nonce],
                ['Timestamp',new Date(block.timestamp * 1000).toLocaleString()]];
            for (const [name, value] of details) {
                const label = document.createElement('dt');
                const text = document.createElement('dd');
                label.textContent = name;
                text.textContent = value;
                fields.append(label, text);
            }
            message.textContent = block.transactions.length + (block.transactions.length === 1 ? ' transaction' : ' transactions');
            for (const tx of block.transactions) {
                const link = document.createElement('a');
                link.className = 'list-group-item list-group-item-action text-break';
                link.href = '/ide?' + new URLSearchParams({tx: tx.tx_id});
                link.textContent = tx.tx_type + ' · ' + tx.tx_id;
                list.append(link);
            }
        } catch (error) {
            if (version === this.detailVersion) message.textContent = error.message;
        }
    }
}
