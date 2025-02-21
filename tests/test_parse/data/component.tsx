interface Props {
  name: string;
  age: number;
}

const UserCard = ({ name, age }: Props) => {
  return (
    <div className="user-card">
      <h2>{name}</h2>
      <p>Age: {age}</p>
    </div>
  );
};

export default UserCard; 