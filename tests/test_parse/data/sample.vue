<template>
  <div class="user-card">
    <h2>{{ name }}</h2>
    <p>Age: {{ age }}</p>
    <p>{{ formatUser() }}</p>
  </div>
</template>

<script>
export default {
  props: {
    name: String,
    age: Number
  },
  methods: {
    formatUser() {
      return `${this.name} (${this.age} years old)`;
    }
  }
}
</script>

<style scoped>
.user-card {
  padding: 1rem;
  border: 1px solid #ccc;
}
</style> 