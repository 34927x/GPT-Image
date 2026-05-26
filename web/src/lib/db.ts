import { MongoClient, type Db } from 'mongodb';
import { env } from './env';
import type { AccessKey, Plan, Job, Image, ExtensionAccount, WorkerHeartbeat } from './types';

declare global {
  // eslint-disable-next-line no-var
  var __mongo: { client: MongoClient | null; promise: Promise<MongoClient> | null };
}

const cache = (globalThis.__mongo ??= { client: null, promise: null });

async function getClient(): Promise<MongoClient> {
  if (cache.client) return cache.client;
  if (!cache.promise) {
    cache.promise = MongoClient.connect(env.MONGODB_URI, {
      serverSelectionTimeoutMS: 8000,
      maxPoolSize: 10,
    });
  }
  cache.client = await cache.promise;
  return cache.client;
}

export async function getDb(): Promise<Db> {
  const client = await getClient();
  return client.db(env.MONGODB_DB);
}

export async function collections() {
  const db = await getDb();
  return {
    keys: db.collection<AccessKey>('keys'),
    plans: db.collection<Plan>('plans'),
    jobs: db.collection<Job>('jobs'),
    images: db.collection<Image>('images'),
    accounts: db.collection<ExtensionAccount>('accounts'),
    heartbeats: db.collection<WorkerHeartbeat>('heartbeats'),
  };
}

let indexesEnsured = false;

export async function ensureIndexes() {
  if (indexesEnsured) return;
  const c = await collections();
  await Promise.all([
    c.keys.createIndex({ key: 1 }, { unique: true }),
    c.keys.createIndex({ revoked: 1 }),
    c.plans.createIndex({ name: 1 }, { unique: true }),
    c.jobs.createIndex({ status: 1, createdAt: 1 }),
    c.jobs.createIndex({ keyId: 1, createdAt: -1 }),
    c.images.createIndex({ keyId: 1, createdAt: -1 }),
    c.images.createIndex({ jobId: 1 }),
    c.accounts.createIndex({ label: 1 }, { unique: true }),
    c.heartbeats.createIndex({ workerId: 1 }, { unique: true }),
    c.heartbeats.createIndex(
      { lastSeen: 1 },
      { expireAfterSeconds: 60 * 60 * 24 } // auto-clean dead workers after 24h
    ),
  ]);
  indexesEnsured = true;
}
