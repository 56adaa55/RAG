import React, { useState, useEffect } from 'react';
import image1 from '../assets/01.jpg';
import image2 from '../assets/02.jpg';
import image3 from '../assets/03.jpg';
import image4 from '../assets/04.jpg';
import image5 from '../assets/05.jpg';
import image6 from '../assets/06.jpg';
import image7 from '../assets/07.jpg';
import image8 from '../assets/08.jpg';
import image9 from '../assets/09.jpg';
import image10 from '../assets/10.jpg';

const RandomImage = ({ message }) => {
  const [randomImage, setRandomImage] = useState(null);

  useEffect(() => {
    const images = [
      image1, image2, image3, image4, image5,
      image6, image7, image8, image9, image10
    ];
    const randomIdx = Math.floor(Math.random() * images.length);
    setRandomImage(images[randomIdx]);
  }, []);

  return (
    <div className="h-full flex flex-col items-center justify-center text-gray-500 p-6">
      {randomImage && (
        <img 
          src={randomImage} 
          alt="Empty state illustration" 
          className="w-full h-[300px] object-cover mb-4"
        />
      )}
      <p>{message}</p>
    </div>
  );
};

export default RandomImage; 