import { defineStorage } from '@aws-amplify/backend';

// Define a storage bucket for report block details
export const reportBlockDetails = defineStorage({
  name: 'reportBlockDetails',
  access: (allow) => ({
    // Option 1: Combined approach - allow guest read access to all report blocks
    // and authenticated users get additional write/delete permissions to their own files
    'reportblocks/*': [
      allow.guest.to(['read']),
      allow.authenticated.to(['read', 'write', 'delete'])
    ]
  })
}); 