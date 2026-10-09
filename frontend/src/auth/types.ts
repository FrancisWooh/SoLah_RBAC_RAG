export interface CurrentUser {
  user_id: string
  username: string
  department: string | null
  clearance: number
  compartments: string[]
  effective_roles: string[]
}
