import { defineStorage } from '@aws-amplify/backend';

// Define a storage bucket for report block details
export const reportBlockDetails = defineStorage({
  name: 'reportBlockDetails',
  access: (allow) => ({
    // Allow authenticated users to read/write/delete their own report block details
    'reportblocks/{entity_id}/*': [
      allow.authenticated.to(['read', 'write', 'delete'])
    ],
  })
}); 