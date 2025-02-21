<script>
  export let name;
  export let age;
  
  function formatUser() {
    return `${name} (${age} years old)`;
  }
</script>

<div class="user-card">
  <h2>{name}</h2>
  <p>Age: {age}</p>
  <p>{formatUser()}</p>
</div>

<style>
  .user-card {
    padding: 1rem;
    border: 1px solid #ccc;
  }
</style> 