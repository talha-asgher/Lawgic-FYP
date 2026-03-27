"use client";

import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { useEffect } from 'react';

const customIcon = new L.Icon({
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

function MapRecenter({ coords }) {
  const map = useMap();
  useEffect(() => {
    if (coords[0] && coords[1]) {
      map.setView(coords, 15);
    }
  }, [coords, map]);
  return null;
}

export default function Map({ latitude, longitude, name }) {
  const position = [latitude || 0, longitude || 0];

  return (
    <MapContainer 
      center={position} 
      zoom={15} 
      className="w-full h-full z-10"
    >
      <TileLayer 
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" 
      />
      <Marker position={position} icon={customIcon}>
        <Popup>{name}</Popup>
      </Marker>
      <MapRecenter coords={position} />
    </MapContainer>
  );
}