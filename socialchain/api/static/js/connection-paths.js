'use strict';

class ConnectionPaths {
    constructor(userDid, showGlobal) {
        this.userDid = userDid;
        this.showGlobal = showGlobal;
        this.source = document.getElementById('path-source');
        this.target = document.getElementById('path-target');
        this.avoid = document.getElementById('path-avoid');
        this.submit = document.getElementById('path-submit');
        this.reset = document.getElementById('path-clear');
        this.status = document.getElementById('path-status');
        this.results = document.getElementById('path-results');
        this.names = new Map();
        this.request = 0;
        this.result = null;
        this.initialTarget = new URLSearchParams(location.search).get('target');
        document.getElementById('path-form').addEventListener('submit', event => {
            event.preventDefault();
            this.showGlobal();
            this.find();
        });
        for (const field of [this.source, this.target, this.avoid]) {
            field.addEventListener('change', () => {
                this.clear();
                this.updateAvailability();
            });
        }
        this.reset.addEventListener('click', () => this.clear());
    }

    updateProfiles(profiles) {
        const entries = profiles.map(p => [p.did, p.display_name || p.did])
            .sort((a, b) => a[1].localeCompare(b[1]) || a[0].localeCompare(b[0]));
        const signature = JSON.stringify(entries);
        const linked = this.initialTarget;
        this.initialTarget = null;
        if (this.profileSignature !== signature) {
            const saved = [this.source.value || this.userDid, linked || this.target.value, this.avoid.value];
            this.names = new Map(entries);
            const counts = new Map();
            for (const [, name] of entries) counts.set(name, (counts.get(name) || 0) + 1);
            for (const [index, field] of [this.source, this.target, this.avoid].entries()) {
                field.replaceChildren(new Option(index === 2 ? 'None' : 'Choose a profile', ''));
                for (const [did, name] of entries) {
                    const label = counts.get(name) > 1 ? name + ' · ' + did : name;
                    field.add(new Option(label, did));
                }
                field.value = this.names.has(saved[index]) ? saved[index] : '';
            }
            this.profileSignature = signature;
        }
        const oldAvoid = this.avoid.value;
        this.updateAvailability();
        if (linked && !this.names.has(linked)) {
            this.clear('Destination profile is unavailable.');
        } else if (this.result && (!this.source.value || !this.target.value ||
                                   oldAvoid !== this.avoid.value || this.result.avoid !== (this.avoid.value || null))) {
            this.clear('A selected profile is unavailable. Choose another path.');
        } else if ((linked || this.result) && !this.submit.disabled) {
            this.find();
        } else if (!this.source.value || !this.target.value) {
            this.status.textContent = entries.length < 2
                ? 'Add another profile to explore connections.' : 'Choose a start and destination.';
        }
    }

    updateAvailability() {
        for (const option of this.avoid.options) {
            option.disabled = !!option.value && [this.source.value, this.target.value].includes(option.value);
        }
        if (this.avoid.selectedOptions[0]?.disabled) this.avoid.value = '';
        this.submit.disabled = !this.source.value || !this.target.value;
    }

    clear(message = '') {
        ++this.request;
        this.result = null;
        this.results.replaceChildren();
        this.status.textContent = message;
        this.reset.hidden = true;
        this.highlight();
    }

    unavailable() {
        this.clear('Could not refresh the network. Use Refresh to try again.');
    }

    async find() {
        const id = ++this.request;
        const params = new URLSearchParams({source: this.source.value, target: this.target.value});
        if (this.avoid.value) params.set('avoid', this.avoid.value);
        if (!this.result) this.status.textContent = 'Finding a connection path…';
        this.reset.hidden = false;
        try {
            const response = await fetch('/api/social/paths?' + params);
            const result = await response.json();
            if (id !== this.request) return;
            if (!response.ok) throw new Error(result.error || 'Could not find a path.');
            this.result = result;
            this.render();
            this.highlight();
        } catch (error) {
            if (id === this.request) this.clear(error.message);
        }
    }

    render() {
        const {baseline, scenario, avoid} = this.result;
        const names = this.names;
        const describe = route => route.hops === null ? 'No connection path'
            : route.hops === 0 ? 'Same profile · 0 hops' : route.hops + (route.hops === 1 ? ' hop' : ' hops');
        this.status.textContent = scenario ? 'Comparing routes with and without ' + names.get(avoid) + '.'
                                          : describe(baseline);
        this.results.replaceChildren();
        const addRoute = (route, title) => {
            if (title) {
                const heading = document.createElement('div');
                heading.className = 'fw-semibold mt-3';
                heading.textContent = title + ' · ' + describe(route);
                this.results.append(heading);
            }
            if (!route.path.length) return;
            const list = document.createElement('ol');
            list.className = 'mt-2 mb-2';
            for (const did of route.path) {
                const item = document.createElement('li');
                const link = document.createElement('a');
                link.href = '/profile/' + encodeURIComponent(did);
                link.textContent = names.get(did) || did;
                link.title = did;
                item.append(link);
                list.append(item);
            }
            this.results.append(list);
        };
        addRoute(baseline, scenario ? 'Original path' : '');
        if (scenario) addRoute(scenario, 'With exclusion');
        const reach = document.createElement('p');
        reach.className = 'text-secondary mt-2 mb-0';
        reach.textContent = 'Other profiles reachable from the start: ' + baseline.reachable_profiles +
            (scenario ? ' → ' + scenario.reachable_profiles : '');
        this.results.append(reach);
        if (scenario && baseline.path.length) {
            const legend = document.createElement('p');
            legend.className = 'text-secondary mb-0';
            legend.textContent = scenario.path.length
                ? 'Gold shows the path with the exclusion. Dashes mark original-only links.'
                : 'Dashes mark the original path.';
            this.results.append(legend);
        }
    }

    highlight() {
        const result = this.result;
        const path = result ? (result.scenario || result.baseline).path : [];
        const order = new Map(path.map((did, i) => [did, i]));
        const original = new Map((result?.scenario ? result.baseline.path : []).map((did, i) => [did, i]));
        const joins = (edge, positions) =>
            Math.abs(positions.get(edge.source.did) - positions.get(edge.target.did)) === 1;
        d3.selectAll('#network-svg .network-edge')
            .classed('path-original', edge => joins(edge, original))
            .classed('path-selected', edge => joins(edge, order));
        d3.selectAll('#network-svg .network-node')
            .classed('path-member', node => order.has(node.did))
            .classed('path-excluded', node => node.did === result?.avoid);
    }
}
