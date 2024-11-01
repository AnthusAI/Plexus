import React, { useState } from 'react';

const ScorecardDetailView: React.FC = () => {
  const [scorecard, setScorecard] = useState({
    scoreDetails: []
  });

  const [scoreDetails, setScoreDetails] = useState(
    scorecard.scoreDetails ?? []
  );

  return (
    // Your existing code here
  );
};

export default ScorecardDetailView; 