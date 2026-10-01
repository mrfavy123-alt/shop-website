PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  price_minor INTEGER NOT NULL CHECK (price_minor >= 0),
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS cart_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  product_id INTEGER NOT NULL REFERENCES products(id),
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  UNIQUE (user_id, product_id)
);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  status TEXT NOT NULL DEFAULT 'placed' CHECK (status IN ('placed', 'processing', 'shipped', 'delivered', 'cancelled')),
  total_minor INTEGER NOT NULL CHECK (total_minor >= 0),
  shipping_address TEXT NOT NULL,
  confirmation_email_status TEXT NOT NULL DEFAULT 'pending' CHECK (confirmation_email_status IN ('pending', 'sent', 'failed')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  product_id INTEGER NOT NULL REFERENCES products(id),
  product_name TEXT NOT NULL,
  unit_price_minor INTEGER NOT NULL CHECK (unit_price_minor >= 0),
  quantity INTEGER NOT NULL CHECK (quantity > 0)
);

CREATE INDEX IF NOT EXISTS idx_cart_items_user_id ON cart_items(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_user_id_created_at ON orders(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);

CREATE TABLE IF NOT EXISTS bookings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  phone TEXT NOT NULL,
  occasion TEXT NOT NULL,
  event_date TEXT NOT NULL,
  guest_count INTEGER NOT NULL CHECK (guest_count >= 5),
  small_chops TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'requested',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS training_programs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  duration TEXT NOT NULL,
  course_fee_minor INTEGER NOT NULL CHECK (course_fee_minor >= 0),
  materials_fee_minor INTEGER NOT NULL CHECK (materials_fee_minor >= 0),
  materials TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS training_enrollments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  program_id INTEGER NOT NULL REFERENCES training_programs(id),
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  phone TEXT NOT NULL,
  payment_token_hash TEXT NOT NULL,
  total_minor INTEGER NOT NULL CHECK (total_minor >= 0),
  installment_count INTEGER NOT NULL DEFAULT 2 CHECK (installment_count = 2),
  status TEXT NOT NULL DEFAULT 'requested',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS training_payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  enrollment_id INTEGER NOT NULL REFERENCES training_enrollments(id) ON DELETE CASCADE,
  installment_number INTEGER NOT NULL CHECK (installment_number IN (1, 2)),
  amount_minor INTEGER NOT NULL CHECK (amount_minor >= 0),
  payment_reference TEXT UNIQUE,
  status TEXT NOT NULL DEFAULT 'due',
  due_note TEXT NOT NULL,
  paid_at TEXT,
  UNIQUE (enrollment_id, installment_number)
);

CREATE TABLE IF NOT EXISTS contact_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  topic TEXT NOT NULL,
  message TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(event_date);
CREATE INDEX IF NOT EXISTS idx_training_enrollments_email ON training_enrollments(email);
CREATE INDEX IF NOT EXISTS idx_contact_messages_created ON contact_messages(created_at);

INSERT INTO products (id, name, category, price_minor) VALUES
  (1,'Zamac classic burger','Meals',1250000),
  (2,'Crispy chicken burger','Chicken',1050000),
  (3,'Smoky party jollof, chicken & dodo','Rice dishes',1650000),
  (4,'Loaded golden fries','Sides',450000),
  (5,'Pepper grilled chicken','Chicken',1250000),
  (6,'Nigerian fried rice & chicken','Rice dishes',1450000),
  (7,'Creamy chicken alfredo','Continental',1600000),
  (8,'Golden Nigerian meat pie','Pastries',250000),
  (9,'Chilled zobo','Drinks',150000),
  (10,'Small chops sampler','Pastries',850000),
  (11,'Fresh mint lemonade','Drinks',120000),
  (12,'Small chops party tray','Events / Catering',9500000),
  (13,'Peppered goat & fried plantain','Meals',1750000),
  (14,'Chicken stir-fry noodles','Continental',1550000),
  (15,'Puff puff box','Pastries',500000),
  (16,'Grilled peppered asun','Meals',1800000),
  (17,'Grilled peppered snail','Meals',2200000),
  (18,'Egusi soup & swallow','Meals',1450000),
  (19,'Beef suya','Meals',950000),
  (20,'BBQ whole fish','Meals',2800000),
  (21,'Goat head isi ewu','Meals',2500000),
  (22,'Birthday cupcake box','Pastries',1800000),
  (23,'Banana puff puff box','Pastries',600000),
  (24,'Onion puff puff box','Pastries',600000)
ON CONFLICT(id) DO UPDATE SET name=excluded.name, category=excluded.category, price_minor=excluded.price_minor;

INSERT INTO training_programs (code,title,description,duration,course_fee_minor,materials_fee_minor,materials) VALUES
 ('chef','Professional Chef Training','Practical Nigerian and continental cooking, kitchen safety, menu costing and food presentation.','6 weeks',24000000,6500000,'Chef jacket and apron, knife kit, recipe workbook, pantry starter pack'),
 ('nutrition','Nutrition & Dietetics Foundations','Nutrition basics, balanced menu planning, food hygiene and healthy cooking practice.','8 weeks',28000000,4500000,'Nutrition workbook, portion guide, menu-planning cards, measuring kit')
ON CONFLICT(code) DO UPDATE SET title=excluded.title,description=excluded.description,duration=excluded.duration,course_fee_minor=excluded.course_fee_minor,materials_fee_minor=excluded.materials_fee_minor,materials=excluded.materials;
