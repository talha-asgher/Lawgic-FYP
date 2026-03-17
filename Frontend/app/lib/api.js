// frontend/lib/api.js

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function login(email, password) {
  const formData = new URLSearchParams();
  formData.append("username", email); // IMPORTANT
  formData.append("password", password);

  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: formData.toString(),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "Login failed");
  }

  return data;
}



export async function registerUser(formData) {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      name: formData.name,
      email: formData.email,
      password: formData.password,
      phone_num: formData.phone,
      role: "client",
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "User registration failed");
  }

  return data;
}


/* ================= LAWYER REGISTER ================= */

export async function registerLawyer(formData) {
  const response = await fetch(`${API_BASE_URL}/auth/register-lawyer`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      name: formData.fullName,
      email: formData.email,
      password: formData.password,
      phone_num: formData.phone,

      specialization: formData.specialization,
      bio_data: formData.bio,
      years_of_experience: Number(formData.experience),
      office_address: formData.officeAddress,
      consultation_fee: Number(formData.hourlyRate),
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "Lawyer registration failed");
  }

  return data;
}