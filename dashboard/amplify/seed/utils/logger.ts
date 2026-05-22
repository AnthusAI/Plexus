export class Logger {
  private startTime: number = Date.now();

  start(message: string): void {
    console.log('\n' + '='.repeat(80));
    console.log(`🚀 ${message}`);
    console.log('='.repeat(80) + '\n');
    this.startTime = Date.now();
  }

  phase(message: string): void {
    console.log('\n' + '-'.repeat(80));
    console.log(`📋 PHASE: ${message}`);
    console.log('-'.repeat(80));
  }

  table(tableName: string, message: string): void {
    console.log(`\n📊 [${tableName}] ${message}`);
  }

  progress(tableName: string, message: string): void {
    console.log(`   [${tableName}] ${message}`);
  }

  info(context: string, message: string): void {
    console.log(`ℹ️  [${context}] ${message}`);
  }

  success(tableName: string, message: string): void {
    console.log(`✅ [${tableName}] ${message}`);
  }

  warn(tableName: string, message: string): void {
    console.warn(`⚠️  [${tableName}] ${message}`);
  }

  error(tableName: string, message: string): void {
    console.error(`❌ [${tableName}] ${message}`);
  }

  complete(message: string): void {
    const elapsed = ((Date.now() - this.startTime) / 1000).toFixed(1);
    console.log('\n' + '='.repeat(80));
    console.log(`✨ ${message}`);
    console.log(`⏱️  Total time: ${elapsed}s`);
    console.log('='.repeat(80) + '\n');
  }
}
