import type { ObjectId } from 'mongodb';

/* ============ ACCESS KEYS ============ */

export interface Plan {
  _id?: ObjectId;
  name: string;
  dailyImageLimit: number; // 0 = unlimited
  totalImageLimit: number; // 0 = unlimited
  validityDays: number; // 0 = no expiry
  description?: string;
  createdAt: Date;
}

export interface AccessKey {
  _id?: ObjectId;
  key: string; // e.g., BGT-XXXX-XXXX-XXXX
  planName: string;
  note?: string; // admin note: "sold to X" etc.
  createdAt: Date;
  expiresAt: Date | null;
  revoked: boolean;
  totalUsed: number;
  dailyUsed: number;
  dailyResetAt: Date;
  lastUsedAt?: Date | null;
  isAdmin?: boolean; // true for the master admin key
}

/* ============ JOBS / IMAGES ============ */

export type JobStatus = 'pending' | 'processing' | 'done' | 'failed';

export interface Job {
  _id?: ObjectId;
  keyId: ObjectId; // owner
  prompt: string;
  imageSize: '1:1' | '16:9' | '9:16' | '4:3';
  status: JobStatus;
  workerId?: string | null;
  account?: string | null;
  error?: string | null;
  imageId?: ObjectId | null;
  createdAt: Date;
  startedAt?: Date | null;
  finishedAt?: Date | null;
  attempts: number;
  batchId?: string;
}

export interface Image {
  _id?: ObjectId;
  jobId: ObjectId;
  keyId: ObjectId;
  prompt: string;
  url: string; // cloudinary URL or data URI
  storage: 'cloudinary' | 'mongodb';
  account?: string;
  createdAt: Date;
}

/* ============ EXTENSION ACCOUNTS (CHATGPT) ============ */

export interface ExtensionAccount {
  _id?: ObjectId;
  label: string;
  cookies: Array<{
    name: string;
    value: string;
    domain: string;
    path?: string;
    secure?: boolean;
    httpOnly?: boolean;
    sameSite?: string;
    expires?: number;
  }>;
  workerId?: string;
  active: boolean;
  expired: boolean;
  rateLimited: boolean;
  rateLimitResetAt?: Date | null;
  errorCount: number;
  lastUsedAt?: Date | null;
  createdAt: Date;
}

/* ============ WORKER HEARTBEAT ============ */

export interface WorkerHeartbeat {
  _id?: ObjectId;
  workerId: string;
  label?: string;
  version?: string;
  accountsTotal: number;
  accountsActive: number;
  jobsToday: number;
  lastSeen: Date;
}
