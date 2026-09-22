// AuthContext.tsx
import { useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { api, clearTokens, getAccessToken, AUTH_LOGOUT_EVENT } from '../api/client';
import { AuthContext } from './auth';
import type { User } from './auth';

// useAuth 與 User 型別放在 ./auth.ts（原因見該檔開頭）

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);

  // App 初始化時，用手上的 access token 還原登入狀態。
  // token 過期的話，api client 的攔截器會自動續命後重送，這裡不用管。
  useEffect(() => {
    const fetchProfile = async () => {
      if (!getAccessToken()) {
        setUser(null);
        return;
      }
      try {
        const res = await api.get<User>('/me/');
        setUser(res.data);
      } catch {
        // 連 refresh 都失敗（攔截器已清掉 token）
        setUser(null);
      }
    };
    fetchProfile();
  }, []);

  // 攔截器在續命失敗時會廣播這個事件，這裡同步把畫面上的登入狀態收掉
  useEffect(() => {
    const onForcedLogout = () => setUser(null);
    window.addEventListener(AUTH_LOGOUT_EVENT, onForcedLogout);
    return () => window.removeEventListener(AUTH_LOGOUT_EVENT, onForcedLogout);
  }, []);

  const logout = async () => {
    if (window.confirm('確定要登出嗎？')) {
      try {
        await api.post('/logout/', {});
      } catch {
        // 後端沒做 logout 也沒關係
      } finally {
        clearTokens();
        setUser(null);
        alert('您已成功登出');
      }
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        setUser,
        logout,
        isAuthenticated: !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

