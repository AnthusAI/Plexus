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
    ],
    // Add access for scoreresults path within this bucket as well, if files are here
    'scoreresults/*': [
      allow.guest.to(['read']), // Assuming guests might also need read if they can see the card
      allow.authenticated.to(['read']) // Authenticated users need to read
    ]
  })
});

// Define a storage bucket for item attachments
export const attachments = defineStorage({
  name: 'attachments',
  isDefault: true,
  access: (allow) => ({
    'datasources/*': [
      allow.guest.to(['read']),
      allow.authenticated.to(['read', 'write', 'delete'])
    ],
    'datasets/*': [
      allow.guest.to(['read']),
      allow.authenticated.to(['read', 'write', 'delete'])
    ],
  })
});

// Define a storage bucket for score result attachments
// This definition might be for a separate bucket. If the scoreresults files are in reportBlockDetailsBucket,
// then the rules above are more relevant for the read operation.
export const scoreResultAttachments = defineStorage({
  name: 'scoreResultAttachments',
  access: (allow) => ({
    'scoreresults/*': [
      allow.guest.to(['read']),
      allow.authenticated.to(['read', 'write', 'delete'])
    ]
  })
});

// Define a storage bucket for dataset files
export const datasets = defineStorage({
  name: 'datasets',
  access: (allow) => ({
    'datasets/*': [
      allow.guest.to(['read']),
      allow.authenticated.to(['read', 'write', 'delete'])
    ]
  })
}); 