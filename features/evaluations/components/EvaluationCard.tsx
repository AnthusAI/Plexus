function isValidStatus(status: string | undefined): status is 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' {
  return status === 'PENDING' || status === 'RUNNING' || status === 'COMPLETED' || status === 'FAILED';
}

status: isValidStatus(stage.status) ? stage.status : 'PENDING', 