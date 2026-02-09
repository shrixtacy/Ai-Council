// Email validation
export function validateEmail(email: string): string | null {
  if (!email) {
    return 'Email is required'
  }
  
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(email)) {
    return 'Please enter a valid email address'
  }
  
  return null
}

// Password validation
export function validatePassword(password: string): string | null {
  if (!password) {
    return 'Password is required'
  }
  
  if (password.length < 8) {
    return 'Password must be at least 8 characters'
  }
  
  if (!/[A-Z]/.test(password)) {
    return 'Password must contain at least one uppercase letter'
  }
  
  if (!/[0-9]/.test(password)) {
    return 'Password must contain at least one number'
  }
  
  return null
}

// Name validation
export function validateName(name: string): string | null {
  if (!name) {
    return 'Name is required'
  }
  
  if (name.length < 2) {
    return 'Name must be at least 2 characters'
  }
  
  if (name.length > 100) {
    return 'Name must be less than 100 characters'
  }
  
  return null
}

// Password strength calculation
export interface PasswordStrength {
  score: number // 0-4
  label: string
  color: string
}

export function getPasswordStrength(password: string): PasswordStrength {
  if (!password) {
    return { score: 0, label: 'None', color: 'gray' }
  }
  
  let score = 0
  
  // Length checks
  if (password.length >= 8) score++
  if (password.length >= 12) score++
  
  // Character type checks
  if (/[a-z]/.test(password)) score++
  if (/[A-Z]/.test(password)) score++
  if (/[0-9]/.test(password)) score++
  if (/[^a-zA-Z0-9]/.test(password)) score++
  
  // Normalize score to 0-4
  score = Math.min(4, Math.floor(score / 1.5))
  
  const labels: Record<number, { label: string; color: string }> = {
    0: { label: 'Very Weak', color: 'red' },
    1: { label: 'Weak', color: 'orange' },
    2: { label: 'Fair', color: 'yellow' },
    3: { label: 'Strong', color: 'lime' },
    4: { label: 'Very Strong', color: 'green' },
  }
  
  return { score, ...labels[score] }
}
