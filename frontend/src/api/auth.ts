import { api } from './client'
import { API_ENDPOINTS } from '../constants/apiEndpoints'
import type { User } from '../types/auth'

export interface LoginResponse {
  access_token: string
  refresh_token: string
  user: User
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  return api.post<LoginResponse>(API_ENDPOINTS.auth.login, { username, password })
}

export async function register(username: string, email: string, password: string): Promise<{ message: string; user_id: string }> {
  return api.post(API_ENDPOINTS.auth.register, { username, email, password })
}

export async function fetchMe(): Promise<User> {
  return api.get<User>(API_ENDPOINTS.auth.me)
}

export async function logout(): Promise<void> {
  return api.post(API_ENDPOINTS.auth.logout)
}
