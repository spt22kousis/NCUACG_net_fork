// frontend/src/contexts/auth.ts
// AuthContext 物件、型別與 useAuth hook。
// 跟 AuthContext.tsx（只放 <AuthProvider> 元件）分開，是因為 Vite 的 Fast Refresh
// 要求 .tsx 檔只匯出元件；hook 跟元件放在同一個檔案，改一行就會整頁重新載入、狀態全丟。
import { createContext, useContext } from 'react';
import type { Dispatch, SetStateAction } from 'react';

export interface User {
  id: number;
  username: string;
  role: 'superadmin' | 'admin' | 'member' | 'guest';
}

export interface AuthContextType {
  user: User | null;
  setUser: Dispatch<SetStateAction<User | null>>;
  logout: () => Promise<void>;
  isAuthenticated: boolean;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth 必須在 AuthProvider 裡面使用');
  }
  return context;
};
