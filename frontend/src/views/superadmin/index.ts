/**
 * Owner Console Views (legacy barrel)
 *
 * Platform-level administration views for managing tenants,
 * monitoring system health, and overseeing platform operations.
 * Most of these views now live under views/console/*; TenantsList
 * and TenantProfile remain here pending their Task D3 removal.
 */

export { default as ControlTower } from '../console/ControlTower'
export { default as TenantsList } from './TenantsList'
export { default as TenantProfile } from './TenantProfile'
export { default as Benchmarks } from '../console/Benchmarks'
export { default as Audit } from '../console/Audit'
export { default as System } from '../console/System'
