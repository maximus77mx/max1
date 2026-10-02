import { createContext, useContext } from 'react';

export const AuthContext = createContext({ user: null, can: () => false, logout: () => {} });
export const useAuth = () => useContext(AuthContext);

export const ROLE_BADGE = {
  super_admin: { label: 'Super Admin', color: '#e60023' },
  admin: { label: 'Admin', color: '#7e238b' },
  editor: { label: 'Editor', color: '#1f5bb5' },
  owner: { label: 'Owner', color: '#915b00' },
  viewer: { label: 'Viewer', color: '#62625b' },
};
