/**
 * Stratum AI - Admin API
 *
 * User and tenant management endpoints (Super Admin)
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient, ApiResponse, PaginatedResponse } from './client'

// Types
export type UserRole = 'owner' | 'admin' | 'user' | 'viewer'

export interface User {
  id: number
  email: string
  name: string
  role: UserRole
  tenantId: number | null
  isActive: boolean
  isVerified: boolean
  lastLoginAt: string | null
  createdAt: string
  updatedAt: string
}

export interface UserFilters {
  role?: UserRole
  tenantId?: number
  isActive?: boolean
  search?: string
  skip?: number
  limit?: number
}

export interface CreateUserRequest {
  email: string
  name: string
  password: string
  role: UserRole
  tenantId?: number
}

export interface UpdateUserRequest {
  name?: string
  role?: UserRole
  tenantId?: number
  isActive?: boolean
}

// API Functions
export const adminApi = {
  // User Management
  getUsers: async (filters: UserFilters = {}): Promise<PaginatedResponse<User>> => {
    const response = await apiClient.get<ApiResponse<PaginatedResponse<User>>>(
      '/admin/users',
      { params: filters }
    )
    return response.data.data
  },

  getUser: async (id: number): Promise<User> => {
    const response = await apiClient.get<ApiResponse<User>>(`/admin/users/${id}`)
    return response.data.data
  },

  createUser: async (data: CreateUserRequest): Promise<User> => {
    const response = await apiClient.post<ApiResponse<User>>('/admin/users', data)
    return response.data.data
  },

  updateUser: async (id: number, data: UpdateUserRequest): Promise<User> => {
    const response = await apiClient.patch<ApiResponse<User>>(`/admin/users/${id}`, data)
    return response.data.data
  },

  deleteUser: async (id: number): Promise<void> => {
    await apiClient.delete(`/admin/users/${id}`)
  },

  resetUserPassword: async (id: number): Promise<{ temporaryPassword: string }> => {
    const response = await apiClient.post<ApiResponse<{ temporaryPassword: string }>>(
      `/admin/users/${id}/reset-password`
    )
    return response.data.data
  },
}

// React Query Hooks

// User hooks
export function useUsers(filters: UserFilters = {}) {
  return useQuery({
    queryKey: ['admin', 'users', filters],
    queryFn: () => adminApi.getUsers(filters),
    staleTime: 30 * 1000,
  })
}

export function useUser(id: number) {
  return useQuery({
    queryKey: ['admin', 'users', id],
    queryFn: () => adminApi.getUser(id),
    enabled: !!id,
  })
}

export function useCreateUser() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: adminApi.createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })
}

export function useUpdateUser() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateUserRequest }) =>
      adminApi.updateUser(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'users', variables.id] })
    },
  })
}

export function useDeleteUser() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: adminApi.deleteUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })
}

export function useResetUserPassword() {
  return useMutation({
    mutationFn: adminApi.resetUserPassword,
  })
}
