import { uploadData, list, downloadData } from 'aws-amplify/storage';
import type { SeedContext } from '../types';

export async function syncStorageBuckets(context: SeedContext): Promise<void> {
  const { config, logger, daysRecent } = context;
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - daysRecent);

  logger.info('S3', `Syncing ${config.s3Buckets.length} storage buckets`);
  logger.info('S3', `Filtering files modified after: ${cutoffDate.toISOString()}`);

  for (const bucket of config.s3Buckets) {
    logger.progress('S3', `Syncing bucket: ${bucket}`);
    let syncedCount = 0;
    let syncedBytes = 0;
    const maxBytes = 5 * 1024 * 1024 * 1024; // 5GB limit

    try {
      // List files from production (via production credentials)
      const listResult = await list({
        path: `${bucket}/`,
        options: {
          listAll: true
        }
      });

      // Filter by date
      const files = (listResult.items || []).filter(item => {
        if (!item.lastModified) return false;
        const lastModified = new Date(item.lastModified);
        return lastModified >= cutoffDate;
      });

      logger.info('S3', `Found ${files.length} recent files in ${bucket}`);

      for (const file of files) {
        if (syncedBytes >= maxBytes) {
          logger.warn('S3', `Reached 5GB limit for ${bucket}, skipping remaining files`);
          break;
        }

        try {
          // Download from production
          const downloadResult = await downloadData({
            path: file.path!
          }).result;

          const blob = await downloadResult.body.blob();
          syncedBytes += blob.size;

          // Upload to sandbox
          await uploadData({
            path: file.path!,
            data: blob
          }).result;

          syncedCount++;

          if (syncedCount % 10 === 0) {
            logger.progress(
              'S3',
              `${bucket}: ${syncedCount} files (${(syncedBytes / 1024 / 1024).toFixed(2)} MB)`
            );
          }
        } catch (error: any) {
          logger.warn('S3', `Failed to sync ${file.path}: ${error.message}`);
        }
      }

      logger.success(
        'S3',
        `${bucket}: ${syncedCount} files synced (${(syncedBytes / 1024 / 1024).toFixed(2)} MB)`
      );
    } catch (error: any) {
      logger.error('S3', `Failed to sync bucket ${bucket}: ${error.message}`);
    }
  }
}
