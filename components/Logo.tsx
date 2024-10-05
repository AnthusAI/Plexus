import React from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faComments } from '@fortawesome/free-solid-svg-icons';

const Logo = () => {
  return (
    <div className="flex items-center space-x-4">
      <FontAwesomeIcon 
        icon={faComments} 
        className="text-blue-500 text-4xl"
      />
      <div>
        <h1 className="text-3xl font-bold text-gray-800">Plexus</h1>
        <p className="text-sm text-gray-600">AI scoring at scale</p>
      </div>
    </div>
  );
};

export default Logo;