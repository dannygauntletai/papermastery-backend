# WebSocket API Documentation

## Overview

The PaperMastery platform uses Socket.io to provide real-time updates for various features like session bookings, researcher availability, payment confirmations, and researcher onboarding. This document outlines how to connect to and use the WebSocket API.

## Connection

**Connection URL:** `https://YOUR_DOMAIN/socket.io`

When connecting to the Socket.io server, you must provide a user ID as a query parameter:

```javascript
import { io } from 'socket.io-client';

const socket = io('https://YOUR_DOMAIN/socket.io', {
  query: {
    userId: 'USER_UUID_HERE'
  },
  transports: ['websocket', 'polling']
});

socket.on('connect', () => {
  console.log('Connected to WebSocket server');
});

socket.on('connection_success', (data) => {
  console.log('Connection successful', data);
});

socket.on('connect_error', (error) => {
  console.log('Connection error:', error);
});
```

## Available Events

### Client-to-Server Events

These are events you can emit from the frontend to the server:

#### `join_session_room`

Join a room to receive updates about a specific session.

```javascript
socket.emit('join_session_room', { session_id: 'SESSION_UUID' }, (response) => {
  console.log('Joined session room:', response);
});
```

#### `leave_session_room`

Leave a session room when you no longer need updates.

```javascript
socket.emit('leave_session_room', { session_id: 'SESSION_UUID' }, (response) => {
  console.log('Left session room:', response);
});
```

#### `join_researcher_room`

Join a room to receive updates about a specific researcher (availability, status changes).

```javascript
socket.emit('join_researcher_room', { researcher_id: 'RESEARCHER_UUID' }, (response) => {
  console.log('Joined researcher room:', response);
});
```

### Server-to-Client Events

These are events you should listen for to receive real-time updates:

#### `session_update`

Triggered when there's an update to a session you're following.

```javascript
socket.on('session_update', (data) => {
  console.log('Session update:', data);
  // Handle session update (status change, researcher joined, etc.)
});
```

#### `booking_confirmation`

Triggered when a booking is confirmed.

```javascript
socket.on('booking_confirmation', (data) => {
  console.log('Booking confirmed:', data);
  // Update UI to show booking confirmation
});
```

#### `availability_update`

Triggered when a researcher's availability changes.

```javascript
socket.on('availability_update', (data) => {
  console.log('Availability updated:', data);
  // Update calendar or booking form
});
```

#### `payment_update`

Triggered when there's an update to a payment.

```javascript
socket.on('payment_update', (data) => {
  console.log('Payment update:', data);
  // Show payment notification, update UI
});
```

#### `researcher_onboarded`

Triggered when a researcher you've requested joins the platform.

```javascript
socket.on('researcher_onboarded', (data) => {
  console.log('Researcher onboarded:', data);
  // Show notification, update researcher list
});
```

## Integration Examples

### Booking Form Component

```javascript
import React, { useEffect } from 'react';
import { io } from 'socket.io-client';
import { useAuth } from '../contexts/AuthContext';

function BookingForm({ researcherId }) {
  const { user } = useAuth();
  const [socket, setSocket] = useState(null);
  
  useEffect(() => {
    // Connect to WebSocket
    const socketInstance = io('/socket.io', {
      query: { userId: user.id }
    });
    
    setSocket(socketInstance);
    
    // Join the researcher room to get availability updates
    socketInstance.emit('join_researcher_room', { researcher_id: researcherId });
    
    // Listen for availability updates
    socketInstance.on('availability_update', (data) => {
      // Update available time slots
      updateAvailableTimeSlots(data);
    });
    
    // Listen for booking confirmation
    socketInstance.on('booking_confirmation', (data) => {
      // Show confirmation message
      showConfirmation(data);
    });
    
    return () => {
      socketInstance.disconnect();
    };
  }, [user.id, researcherId]);
  
  // Rest of component...
}
```

### Payment Status Component

```javascript
function PaymentStatus({ paymentId, userId }) {
  const [status, setStatus] = useState('pending');
  
  useEffect(() => {
    const socket = io('/socket.io', {
      query: { userId }
    });
    
    socket.on('payment_update', (data) => {
      if (data.payment_id === paymentId) {
        setStatus(data.status);
        
        if (data.status === 'completed') {
          // Show success message or redirect
        }
      }
    });
    
    return () => {
      socket.disconnect();
    };
  }, [paymentId, userId]);
  
  return (
    <div className="payment-status">
      <p>Payment Status: {status}</p>
      {/* Rest of component */}
    </div>
  );
}
```

## Best Practices

1. **Disconnect When Not Needed**: Always disconnect from the Socket.io server when the component unmounts or the user navigates away.

2. **Handle Reconnection**: Socket.io handles reconnection automatically, but you should consider showing a UI indicator when connection is lost.

3. **Room Management**: Only join rooms that are relevant to the current user view. Leave rooms when they are no longer needed.

4. **Error Handling**: Always include error handlers for WebSocket operations.

## Support

For any issues with the WebSocket API, please contact the development team. 