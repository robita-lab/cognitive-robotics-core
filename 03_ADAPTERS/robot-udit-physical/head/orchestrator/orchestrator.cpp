#include "orchestrator.h"

std::mutex mtx_cout; //mutex protecting global variable cout

void printmutex(std::ostream& os, std::string name, std::string msg){
  std::unique_lock<std::mutex> unique_cout(mtx_cout);
  os << "[" << name << "]: "<< msg << std::endl;
}


std::ostream& operator<<(std::ostream &os, const Msg &m) {
  os << "Msg from " << m.src << " to " << m.dst << " with value " << m.value << " and content: " << m.msg;
  return os;
}


std::ostream& operator<<(std::ostream& os, const Params& p) {
  if (p.m == nullptr) {
    os << "Params: k = " << p.k << " m = nullptr";
  } else {
    os << "Params: k = " << p.k << " m = " << *p.m;
  }
  return os;
}
    
std::ostream& operator<<(std::ostream& os, const NeckParams& p) {
  if (p.other == nullptr) {
    os << "NeckParams: other = nullptr";
  } else {
    os << "NeckParams: other = " << p.other;
  }
  return os;
}

//WORKER
void worker::work(Params* p) {
  //std::stringstream ss;
  //ss << *p;
  //ESP_LOGI(pcTaskGetName(nullptr), "[%d]Thworker.work() Params received: %s", worker_id, ss.str().c_str());
  //ESP_LOGD(pcTaskGetName(nullptr), "[%d]Thworker.work() before setup", worker_id);
  
  this->setup(p);
  while (!terminate) {//attribute terminate is controlled by orchestrator
    //printmutex(std::cout, name, "Need to continue working...");
    if (!terminate) {
      // if (!p->blocking)
      //     p->m = queue.try_pop(); // might return nullptr
      // else
      //ESP_LOGI(pcTaskGetName(nullptr), "[%d]Thworker.work() before pop ", worker_id);  
      p->m = popMsg();//blocking as in sockets
      //std::stringstream ss2;
      //ss2 << p->m;
      //ESP_LOGI(pcTaskGetName(nullptr), "[%d]Thworker.work() Msg received: %s", worker_id, ss2.str().c_str());
      //critical section
      this->criticalSection(p);
      //critical section end
      //std::stringstream ss3;
      //ss3 << p->m;
      //ESP_LOGI(pcTaskGetName(nullptr), "[%d]Thworker.work() Msg processed: %s", worker_id, ss3.str().c_str());
    }
    //when working normally or when terminating:
    worker_turn = false;
    // manual unlocking is done before notifying, to avoid waking up
    // the waiting thread only to block again (see notify_one for details)
  }
  this->wrapUp(p);
  printmutex(std::cout, name, "Work finished");
  
}//std::unique_lock invokes unlock when exiting the scope, in this case the function

//this method can be virtual and subclasses reimplement it accordingly
//once the derived classes have this implemented, remove!
void worker::criticalSection(){
  a++;
}

//NECK
void neck::setup(Params* p) {
  RCLCPP_DEBUG_STREAM(node->get_logger(), "[" << worker_id << "]neck.setup():  Params received: " << *p);
}
  
void neck::criticalSection(Params* p) {
  //receive movement/gesture order and play it when the schedule coordinates
  //for the time being just log it
  RCLCPP_DEBUG_STREAM(node->get_logger(), "[" << worker_id << "]neck.criticalSection(): Params received: " << *p);
  NeckParams* neckParams = static_cast<NeckParams*>(p);
  RCLCPP_DEBUG_STREAM(node->get_logger(), "[" << worker_id << "]neck.criticalSection(): NeckParams received: " << *neckParams);
  //critical section
  //++incParams->m->value;
  //critical section end
  //ESP_LOGI(pcTaskGetName(nullptr), "neck.criticalsection() after incrementing");
  //mandar mensaje a la cola del otro thread
  //incParams->m->dst = incParams->other->worker_id;
  //incParams->m->src = worker_id;
  //ESP_LOGI(pcTaskGetName(nullptr), "[%d]neck.criticalsection() before sending msg %d", worker_id, incParams->m->value);
  //RCLCPP_DEBUG_STREAM(node->get_logger(), "[" << worker_id << "]neck.criticalSection(): before sending msg " << incParams->m->value);
  //incParams->other->wrapth.pushMsg(incParams->m);
  //incParams->keepwork = --incParams->k > 0;
  
  
}

void neck::wrapUp(Params* p) {
  //NeckParams* incParams = static_cast<NeckParams*>(p);
  //print value of a
  //std::stringstream ss;
  //ss << "Valor de a: " << incParams->m->value;
  //ESP_LOGI(pcTaskGetName(nullptr), "[%d]neck.wrapUp(): ", worker_id, ss.str().c_str());
}

//EYES
void eyes::setup(Params* p) {
  RCLCPP_DEBUG_STREAM(node->get_logger(), "[" << worker_id << "]eyes.setup():  Params received: " << *p);
}
  
void eyes::criticalSection(Params* p) {
  //receive movement/gesture order and play it when the schedule coordinates
  //for the time being just log it
  RCLCPP_DEBUG_STREAM(node->get_logger(), "[" << worker_id << "]eyes.criticalSection(): Params received: " << *p);
  NeckParams* neckParams = static_cast<NeckParams*>(p);
  RCLCPP_DEBUG_STREAM(node->get_logger(), "[" << worker_id << "]eyes.criticalSection(): NeckParams received: " << *neckParams);
  //critical section
  //++incParams->m->value;
  //critical section end
  //ESP_LOGI(pcTaskGetName(nullptr), "neck.criticalsection() after incrementing");
  //mandar mensaje a la cola del otro thread
  //incParams->m->dst = incParams->other->worker_id;
  //incParams->m->src = worker_id;
  //ESP_LOGI(pcTaskGetName(nullptr), "[%d]neck.criticalsection() before sending msg %d", worker_id, incParams->m->value);
  //RCLCPP_DEBUG_STREAM(node->get_logger(), "[" << worker_id << "]neck.criticalSection(): before sending msg " << incParams->m->value);
  //incParams->other->wrapth.pushMsg(incParams->m);
  //incParams->keepwork = --incParams->k > 0;
  
  
}

void eyes::wrapUp(Params* p) {
  //EyesParams* incParams = static_cast<EyesParams*>(p);
  //print value of a
  //std::stringstream ss;
  //ss << "Valor de a: " << incParams->m->value;
  //ESP_LOGI(pcTaskGetName(nullptr), "[%d]eyes.wrapUp(): ", worker_id, ss.str().c_str());
}


//main loop
//let's use mod == 0 always for the orchestrator and mod == 1 for workers
void orchestrator::assign_tasks(int k){
  const unsigned int mod = 0;
  while (k >= 0){//simulating a fixed ammount of tasks, othw read the schedule and generate appropriate msgs for neck and eyes, then sleep
    for (auto it = allworkers->begin(); it != allworkers->end(); ++it){
      //this is the shared memory version
      //std::mutex* mtx_worker = &it->second->mtx_worker;
      //std::condition_variable* cv = &it->second->cond_worker;
      //bool* worker_turn = &it->second->worker_turn; 
      //std::unique_lock<std::mutex> unique_worker(*mtx_worker);//std::unique_lock with this constructor also invokes lock
      //cv->wait(unique_worker, [worker_turn] { return *worker_turn == false; });
      //if (k == 0){//just after all iterations we flag the worker that next turn is to terminate
      //	it->second->terminate = true;
      //}
      //
      ////TODO:prepare pending_tasks of worker
      //
      ////pass turn to worker EVEN WHEN TERMINATING
      //*worker_turn = true;
      //unique_worker.unlock();
      //cv->notify_one(); //notify worker that it can work now

      //message passing version
      std::stringstream ss;
      ss << "orden " << k;
      Msg* m = new Msg(orch_id, it->second->worker_id, k, ss.str());
      it->second->pushMsg(m);
      sleep(ORCH_WINDOW);
      
    }
    k--;
  }
}

//void respond(){
//  
//}

//void setllm_response(std::string _llm_response){ llm_response = _llm_response;  }
//  
//};


//int main(){
  //std::cout << "Hello CMake." << std::endl;
  //int workcycles = 10000;
  //std::map<std::string, worker*>* allworkers = new std::map<std::string, worker*>();
  //worker* wk = new worker("speech");
  //const auto [it_speech, success] = allworkers->insert({"speech", wk});
  ////if (!success)
  //wk = new worker("speech2");
  //const auto [it_speech2, success2] = allworkers->insert({"speech2", wk});
  ////if (!success)
  //wk = new worker("speech3");
  //const auto [it_speech3, success3] = allworkers->insert({"speech3", wk});
  ////if (!success)
  //wk = new worker("speech4");
  //const auto [it_speech4, success4] = allworkers->insert({"speech4", wk});
  ////if (!success)
  
  //orchestrator* orch = new orchestrator(allworkers, workcycles);
  //delete orch;
  
  //return 0;
//}
