import { createRouter, createWebHistory } from 'vue-router';
import Login from '../views/Login.vue';
import Layout from '../views/Layout.vue';
import VehicleList from '../views/VehicleList.vue';
import DriverList from '../views/DriverList.vue';
import OperationImport from '../views/OperationImport.vue';
import AnalysisIncome from '../views/AnalysisIncome.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login },
    {
      path: '/',
      component: Layout,
      children: [
        { path: '', redirect: '/vehicles' },
        { path: 'vehicles', component: VehicleList },
        { path: 'drivers', component: DriverList },
        { path: 'operations', component: OperationImport },
        { path: 'analysis', component: AnalysisIncome },
      ]
    }
  ]
});

export default router;