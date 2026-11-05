import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const data = JSON.parse(fs.readFileSync(path.join(root, 'src', 'data.json'), 'utf8'));
const errors = [];
const ids = new Set();
const sourceIds = new Set(data.sources.map((source) => source.id));

const register = (id, kind) => {
  if (!id) errors.push(`${kind} missing id`);
  if (ids.has(id)) errors.push(`duplicate id: ${id}`);
  ids.add(id);
};

for (const source of data.sources) register(source.id, 'source');
for (const force of data.aggregate_forces) register(force.id, 'aggregate force');
for (const place of data.locations) {
  register(place.id, 'location');
  if (place.lon < 120 || place.lon > 123 || place.lat < 30 || place.lat > 32.5) {
    errors.push(`coordinate outside Shanghai region: ${place.id}`);
  }
  if (place.kind === 'distribution' && (!place.weapons || !place.rounds)) {
    errors.push(`distribution node missing weapon details: ${place.id}`);
  }
  if (place.people !== undefined) {
    errors.push(`location ${place.id} assigns people, but source only supports citywide totals`);
  }
}
for (const force of data.regional_forces) {
  register(force.id, 'regional force');
  if (force.count !== null) errors.push(`${force.id} must not invent a troop count`);
}

const allRecords = [
  ...data.aggregate_forces,
  ...data.locations,
  ...data.regional_forces,
  ...data.timeline,
  data.instruction
];
for (const record of allRecords) {
  for (const sourceId of record.source_ids ?? []) {
    if (!sourceIds.has(sourceId)) errors.push(`unknown source ${sourceId}`);
  }
}

const concentrated = data.aggregate_forces.find((x) => x.id === 'concentrated');
const standby = data.aggregate_forces.find((x) => x.id === 'standby');
if (concentrated?.count !== 2500) errors.push('concentrated count must be 2,500');
if (standby?.count !== 31000) errors.push('standby count must be 31,000');

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}

console.log(`OK: ${data.locations.length} locations, ${data.aggregate_forces.length} aggregate figures, ${data.sources.length} sources.`);
console.log('Guardrails: no location-level personnel invented; suppression troop counts remain unknown.');
