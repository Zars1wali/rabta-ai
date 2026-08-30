/**
 * High-Throughput Asynchronous Queue for WhatsApp Cloud API Webhooks.
 *
 * Ensures webhook requests return 200 OK within < 100ms by offloading
 * message extraction, deduplication, AI turn generation, and message dispatch.
 */

export interface WhatsAppJobPayload {
  jobId: string;
  tenantId: string;
  rawPayload: unknown;
  receivedAt: string;
  signature?: string;
}

export type WhatsAppJobHandler = (job: WhatsAppJobPayload) => Promise<void>;

export interface WhatsAppMessageQueue {
  enqueue(payload: Omit<WhatsAppJobPayload, 'jobId'>): Promise<string>;
  process(handler: WhatsAppJobHandler): void;
  getPendingCount(): Promise<number>;
  close(): Promise<void>;
}

export class InMemoryWhatsAppQueue implements WhatsAppMessageQueue {
  private queue: WhatsAppJobPayload[] = [];
  private handler: WhatsAppJobHandler | null = null;
  private isProcessing = false;
  private isClosed = false;

  async enqueue(payload: Omit<WhatsAppJobPayload, 'jobId'>): Promise<string> {
    if (this.isClosed) {
      throw new Error('Cannot enqueue job to a closed queue.');
    }

    const jobId = `job_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
    const job: WhatsAppJobPayload = {
      ...payload,
      jobId
    };

    this.queue.push(job);
    this.triggerProcessing();
    return jobId;
  }

  process(handler: WhatsAppJobHandler): void {
    this.handler = handler;
    this.triggerProcessing();
  }

  private triggerProcessing(): void {
    if (this.isProcessing || !this.handler || this.queue.length === 0 || this.isClosed) {
      return;
    }

    this.isProcessing = true;
    queueMicrotask(async () => {
      while (this.queue.length > 0 && !this.isClosed && this.handler) {
        const job = this.queue.shift();
        if (job) {
          try {
            await this.handler(job);
          } catch (err) {
            console.error(`[WhatsAppQueue] Error processing job ${job.jobId}:`, err);
          }
        }
      }
      this.isProcessing = false;
    });
  }

  async getPendingCount(): Promise<number> {
    return this.queue.length;
  }

  /**
   * Helper for tests to wait until all currently queued jobs are processed.
   */
  async waitForDrain(timeoutMs = 5000): Promise<void> {
    const startTime = Date.now();
    while ((this.queue.length > 0 || this.isProcessing) && Date.now() - startTime < timeoutMs) {
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
  }

  async close(): Promise<void> {
    this.isClosed = true;
    this.queue = [];
  }
}
